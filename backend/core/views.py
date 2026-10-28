
from django.db import connection
from django.db.utils import DatabaseError

from rest_framework.decorators import api_view
from rest_framework.response import Response
from rest_framework import status


@api_view(["GET"])
def health_check(request):
    """
    Verifica el estado de la API y la conexión
    con PostgreSQL.
    """

    try:
        with connection.cursor() as cursor:
            cursor.execute("SELECT 1")
            cursor.fetchone()

        return Response(
            {
                "status": "UP",
                "service": "project-management-api",
                "database": "CONNECTED",
                "message": "Backend funcionando correctamente",
            },
            status=status.HTTP_200_OK,
        )

    except DatabaseError:
        return Response(
            {
                "status": "DOWN",
                "service": "project-management-api",
                "database": "DISCONNECTED",
                "message": "No se pudo conectar a PostgreSQL",
            },
            status=status.HTTP_503_SERVICE_UNAVAILABLE,
        )
