from core.access import ProjectScopedViewSetMixin, IsAdministratorForChangeDecision
from rest_framework.permissions import IsAuthenticated
from django.db import transaction
from django.core.exceptions import ValidationError as DjangoValidationError
from django.utils import timezone
from rest_framework import status, viewsets
from rest_framework.decorators import action
from rest_framework.exceptions import ValidationError
from rest_framework.response import Response

from .change_models import ChangeApplication, ChangeEvent, ChangeRequest
from tasks.models import Task
from scheduling.services.schedule_propagation import SchedulePropagationService
from .models import Project
from .change_serializers import (
    ChangeDecisionSerializer, ChangeRequestSerializer, ChangeSubmitSerializer,
    ChangeImplementSerializer, ChangeScheduleSerializer,
    ChangeActualCostSerializer, ChangeCloseSerializer,
)


class ChangeRequestViewSet(ProjectScopedViewSetMixin, viewsets.ModelViewSet):
    """Registro, revisión y decisión con bitácora transaccional.

    La aprobación NO actualiza proyectos, tareas ni presupuestos.
    Las decisiones y aplicaciones registran el usuario autenticado como actor.
    """
    queryset = ChangeRequest.objects.select_related('project').prefetch_related('events').all()
    serializer_class = ChangeRequestSerializer
    permission_classes = [IsAuthenticated, IsAdministratorForChangeDecision]

    def get_queryset(self):
        qs = super().get_queryset()
        project = self.request.query_params.get('project')
        state = self.request.query_params.get('status')
        if project is not None:
            if not project.isdecimal() or int(project) < 1:
                raise ValidationError({'project': 'Debe ser un ID positivo.'})
            qs = qs.filter(project_id=int(project))
        if state is not None:
            if state not in ChangeRequest.Status.values:
                raise ValidationError({'status': 'Estado inválido.'})
            qs = qs.filter(status=state)
        return qs

    @staticmethod
    def _actor_data(request):
        data = request.data.copy()
        data['actor'] = request.user.get_username()
        return data

    @staticmethod
    def _record(change, action, actor, previous='', detail=''):
        ChangeEvent.objects.create(
            change_request=change, action=action, from_status=previous,
            to_status=change.status, actor=actor, detail=detail,
        )

    def perform_create(self, serializer):
        with transaction.atomic():
            project_id = serializer.validated_data['project'].pk
            Project.objects.select_for_update().get(pk=project_id)
            change = serializer.save()
            self._record(change, 'CREATED', self.request.user.get_username(), detail='Solicitud registrada.')

    def perform_update(self, serializer):
        with transaction.atomic():
            # El bloqueo del proyecto se utiliza consistentemente antes del de la solicitud.
            Project.objects.select_for_update().get(pk=serializer.instance.project_id)
            change = ChangeRequest.objects.select_for_update().get(pk=serializer.instance.pk)
            locked = self.get_serializer(change, data=serializer.initial_data, partial=serializer.partial)
            locked.is_valid(raise_exception=True)
            saved = locked.save()
            serializer.instance = saved
            self._record(saved, 'UPDATED', self.request.user.get_username(), previous=saved.status,
                         detail='Campos de la solicitud actualizados.')

    def destroy(self, request, *args, **kwargs):
        return Response(
            {'detail': 'No se eliminan solicitudes: se conserva su trazabilidad.'},
            status=status.HTTP_405_METHOD_NOT_ALLOWED,
        )

    def _transition(self, request, pk, expected, target, action_name, need_reason):
        payload_serializer = ChangeDecisionSerializer if need_reason else ChangeSubmitSerializer
        payload = payload_serializer(data=self._actor_data(request))
        payload.is_valid(raise_exception=True)
        # Primero localizar proyecto; luego bloquear proyecto -> solicitud en ese orden.
        candidate = self.get_object()
        with transaction.atomic():
            Project.objects.select_for_update().get(pk=candidate.project_id)
            change = ChangeRequest.objects.select_for_update().get(pk=candidate.pk)
            if change.status != expected:
                return Response({'detail': f'Operación no permitida desde {change.status}.'},
                                status=status.HTTP_409_CONFLICT)
            if target == ChangeRequest.Status.APPROVED and not change.responsible.strip():
                return Response({'responsible': 'Debe registrar un responsable antes de aprobar.'},
                                status=status.HTTP_400_BAD_REQUEST)
            previous = change.status
            change.status = target
            fields = ['status', 'updated_at']
            if need_reason:
                change.decided_by = payload.validated_data['actor']
                change.decision_reason = payload.validated_data['reason']
                change.decided_at = timezone.now()
                fields += ['decided_by', 'decision_reason', 'decided_at']
            change.save(update_fields=fields)
            self._record(change, action_name, payload.validated_data['actor'],
                         previous=previous, detail=payload.validated_data.get('reason', ''))
        change.refresh_from_db()
        return Response(self.get_serializer(change).data)

    @action(detail=True, methods=['post'], url_path='submit')
    def submit(self, request, pk=None):
        return self._transition(request, pk, ChangeRequest.Status.OPEN,
                                ChangeRequest.Status.UNDER_REVIEW, 'SUBMITTED', False)

    @action(detail=True, methods=['post'], url_path='approve')
    def approve(self, request, pk=None):
        return self._transition(request, pk, ChangeRequest.Status.UNDER_REVIEW,
                                ChangeRequest.Status.APPROVED, 'APPROVED', True)

    @action(detail=True, methods=['post'], url_path='reject')
    def reject(self, request, pk=None):
        return self._transition(request, pk, ChangeRequest.Status.UNDER_REVIEW,
                                ChangeRequest.Status.REJECTED, 'REJECTED', True)

    # Fase 6.2: la escritura serializa proyecto -> solicitud -> tareas.
    # El actor siempre se toma de la sesión validada por Django.
    def _locked_change(self, pk):
        reference = self.get_object()
        Project.objects.select_for_update().get(pk=reference.project_id)
        return ChangeRequest.objects.select_for_update().get(pk=reference.pk)

    @staticmethod
    def _require_status(change, expected):
        if change.status != expected:
            raise ValidationError({'detail': f'Estado requerido: {expected}. Estado actual: {change.status}.'}, code='conflict')

    @staticmethod
    def _model_errors(exc):
        return ValidationError(exc.message_dict if hasattr(exc, 'message_dict') else {'detail': exc.messages})

    @action(detail=True, methods=['post'], url_path='start-implementation')
    def start_implementation(self, request, pk=None):
        payload = ChangeImplementSerializer(data=self._actor_data(request))
        payload.is_valid(raise_exception=True)
        with transaction.atomic():
            change = self._locked_change(pk)
            self._require_status(change, ChangeRequest.Status.APPROVED)
            before = change.status
            change.status = ChangeRequest.Status.IMPLEMENTING
            if 'committed_date' in payload.validated_data:
                change.committed_date = payload.validated_data['committed_date']
            change.save(update_fields=['status', 'committed_date', 'updated_at'])
            self._record(change, 'IMPLEMENTING', payload.validated_data['actor'], previous=before,
                         detail='Implementación iniciada.')
        return Response(self.get_serializer(ChangeRequest.objects.get(pk=change.pk)).data)

    @action(detail=True, methods=['post'], url_path='preview-schedule')
    def preview_schedule(self, request, pk=None):
        payload = ChangeScheduleSerializer(data=self._actor_data(request))
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with transaction.atomic():
            change = self._locked_change(pk)
            if change.status not in (ChangeRequest.Status.APPROVED, ChangeRequest.Status.IMPLEMENTING):
                raise ValidationError({'detail': 'Debe existir una solicitud aprobada.'})
            task = Task.objects.filter(pk=data['task_id'], project_id=change.project_id).first()
            if task is None:
                raise ValidationError({'task_id': 'La actividad no pertenece a este proyecto.'})
            try:
                result = SchedulePropagationService.propagate(
                    task_id=task.pk, start_date=data['start_date'],
                    duration_days=data['duration_days'], commit=False,
                )
            except DjangoValidationError as exc:
                raise self._model_errors(exc) from exc
        return Response(result)

    @action(detail=True, methods=['post'], url_path='apply-schedule')
    def apply_schedule(self, request, pk=None):
        payload = ChangeScheduleSerializer(data=self._actor_data(request))
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with transaction.atomic():
            change = self._locked_change(pk)
            self._require_status(change, ChangeRequest.Status.IMPLEMENTING)
            task = Task.objects.filter(pk=data['task_id'], project_id=change.project_id).first()
            if task is None:
                raise ValidationError({'task_id': 'La actividad no pertenece a este proyecto.'})
            try:
                result = SchedulePropagationService.propagate(
                    task_id=task.pk, start_date=data['start_date'],
                    duration_days=data['duration_days'], commit=True,
                )
            except DjangoValidationError as exc:
                raise self._model_errors(exc) from exc
            if not result['changes']:
                raise ValidationError({'detail': 'La reprogramación no produjo cambios; no se registró ejecución.'})
            for item in result['changes']:
                ChangeApplication.objects.create(
                    change_request=change, kind=ChangeApplication.Kind.SCHEDULE,
                    actor=data['actor'], task_id=item['task_id'],
                    before={'start_date': item['old_start_date'].isoformat(),
                            'end_date': item['old_end_date'].isoformat()},
                    after={'start_date': item['new_start_date'].isoformat(),
                           'end_date': item['new_end_date'].isoformat(),
                           'estimated_duration_days': item['estimated_duration_days']},
                    detail=data['detail'],
                )
            self._record(change, 'SCHEDULE_APPLIED', data['actor'], previous=change.status,
                         detail=f"Reprogramación aplicada: {result['updated_tasks']} actividades.")
        return Response({'schedule': result, 'change_request': self.get_serializer(ChangeRequest.objects.get(pk=change.pk)).data})

    @action(detail=True, methods=['post'], url_path='record-actual-cost')
    def record_actual_cost(self, request, pk=None):
        payload = ChangeActualCostSerializer(data=self._actor_data(request))
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with transaction.atomic():
            change = self._locked_change(pk)
            self._require_status(change, ChangeRequest.Status.IMPLEMENTING)
            previous = change.actual_cost
            if previous == data['actual_cost']:
                raise ValidationError({'actual_cost': 'El costo no ha cambiado.'})
            change.actual_cost = data['actual_cost']
            change.save(update_fields=['actual_cost', 'updated_at'])
            ChangeApplication.objects.create(
                change_request=change, kind=ChangeApplication.Kind.COST,
                actor=data['actor'],
                before={'actual_cost': str(previous) if previous is not None else None},
                after={'actual_cost': str(data['actual_cost'])}, detail=data['detail'],
            )
            self._record(change, 'COST_RECORDED', data['actor'], previous=change.status,
                         detail='Costo real de la solicitud registrado (no modifica presupuesto base).')
        return Response(self.get_serializer(ChangeRequest.objects.get(pk=change.pk)).data)

    @action(detail=True, methods=['post'], url_path='close')
    def close(self, request, pk=None):
        payload = ChangeCloseSerializer(data=self._actor_data(request))
        payload.is_valid(raise_exception=True)
        data = payload.validated_data
        with transaction.atomic():
            change = self._locked_change(pk)
            self._require_status(change, ChangeRequest.Status.IMPLEMENTING)
            if not ChangeApplication.objects.filter(change_request=change).exists():
                raise ValidationError({'detail': 'Registre una ejecución de cronograma o costo antes de cerrar.'})
            if data['actual_completion_date'] < change.requested_at:
                raise ValidationError({'actual_completion_date': 'No puede preceder la fecha de solicitud.'})
            old = change.status
            change.status = ChangeRequest.Status.CLOSED
            change.actual_completion_date = data['actual_completion_date']
            change.result = data['result']
            change.save(update_fields=['status', 'actual_completion_date', 'result', 'updated_at'])
            self._record(change, 'CLOSED', data['actor'], previous=old, detail=data['result'])
        return Response(self.get_serializer(ChangeRequest.objects.get(pk=change.pk)).data)
