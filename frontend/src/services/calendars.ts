import api from './api'

// ==================================================
// CALENDARIOS LABORALES
// ==================================================

export interface CalendarException {
  id: number
  calendar: number

  date: string
  is_working: boolean

  description: string

  created_at: string
  updated_at: string
}

export interface WorkCalendar {
  id: number
  project: number
  name: string

  monday: boolean
  tuesday: boolean
  wednesday: boolean
  thursday: boolean
  friday: boolean
  saturday: boolean
  sunday: boolean

  working_weekdays: number[]

  exceptions: CalendarException[]

  created_at: string
  updated_at: string
}

export interface WorkCalendarPayload {
  project: number
  name?: string

  monday?: boolean
  tuesday?: boolean
  wednesday?: boolean
  thursday?: boolean
  friday?: boolean
  saturday?: boolean
  sunday?: boolean
}

export interface CalendarExceptionPayload {
  calendar: number
  date: string
  is_working: boolean
  description?: string
}

// ==================================================
// CALENDARIO EFECTIVO
// ==================================================

export interface EffectiveCalendarException {
  date: string
  is_working: boolean
}

export interface EffectiveCalendar {
  project_id: number
  project_code: string

  source: 'default' | 'configured'

  calendar_id: number | null
  working_weekdays: number[]

  exceptions: EffectiveCalendarException[]
}

// ==================================================
// CÁLCULOS DE FECHAS
// ==================================================

export type CalendarOperation = 'end' | 'count' | 'shift' | 'is_working_day'

export interface CalendarCalculationPayload {
  operation: CalendarOperation
  start_date: string

  end_date?: string
  duration_days?: number
  offset_days?: number
}

export interface CalendarCalculationResult {
  project_id: number
  project_code: string

  calendar_source: 'default' | 'configured'
  operation: CalendarOperation

  start_date: string

  end_date?: string
  duration_days?: number

  working_days?: number

  offset_days?: number
  result_date?: string

  is_working?: boolean
}

// ==================================================
// SERVICIO DE CALENDARIOS
// ==================================================

export const calendarService = {
  async list(projectId?: number): Promise<WorkCalendar[]> {
    const response = await api.get<WorkCalendar[]>('/scheduling/calendars/', {
      params: projectId === undefined ? {} : { project: projectId },
    })

    return response.data
  },

  async getById(id: number): Promise<WorkCalendar> {
    const response = await api.get<WorkCalendar>(`/scheduling/calendars/${id}/`)

    return response.data
  },

  async create(payload: WorkCalendarPayload): Promise<WorkCalendar> {
    const response = await api.post<WorkCalendar>('/scheduling/calendars/', payload)

    return response.data
  },

  async update(id: number, payload: Partial<WorkCalendarPayload>): Promise<WorkCalendar> {
    const response = await api.patch<WorkCalendar>(`/scheduling/calendars/${id}/`, payload)

    return response.data
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/scheduling/calendars/${id}/`)
  },

  async getEffective(projectId: number): Promise<EffectiveCalendar> {
    const response = await api.get<EffectiveCalendar>(`/scheduling/projects/${projectId}/calendar/`)

    return response.data
  },

  async calculate(
    projectId: number,
    payload: CalendarCalculationPayload,
  ): Promise<CalendarCalculationResult> {
    const response = await api.post<CalendarCalculationResult>(
      `/scheduling/projects/${projectId}/calculate/`,
      payload,
    )

    return response.data
  },
}

// ==================================================
// SERVICIO DE EXCEPCIONES
// ==================================================

export const calendarExceptionService = {
  async list(calendarId?: number): Promise<CalendarException[]> {
    const response = await api.get<CalendarException[]>('/scheduling/exceptions/', {
      params: calendarId === undefined ? {} : { calendar: calendarId },
    })

    return response.data
  },

  async create(payload: CalendarExceptionPayload): Promise<CalendarException> {
    const response = await api.post<CalendarException>('/scheduling/exceptions/', payload)

    return response.data
  },

  async update(id: number, payload: Partial<CalendarExceptionPayload>): Promise<CalendarException> {
    const response = await api.patch<CalendarException>(`/scheduling/exceptions/${id}/`, payload)

    return response.data
  },

  async remove(id: number): Promise<void> {
    await api.delete(`/scheduling/exceptions/${id}/`)
  },
}
