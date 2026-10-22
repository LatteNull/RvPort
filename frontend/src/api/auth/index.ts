import type { User } from '@/types'

import request from '../request'

export interface LoginPayload {
  username: string
  password: string
}

export interface ChangePasswordPayload {
  currentPassword: string
  newPassword: string
}

export interface UpdateProfilePayload {
  displayName: string | null
}

export interface PasswordResetRequestPayload {
  identifier: string
}

export interface PasswordResetRequestResponse {
  accepted: boolean
}

export interface PasswordResetConfirmPayload {
  token: string
  newPassword: string
}

export interface AcceptInvitationPayload {
  token: string
  newPassword: string
}

export interface LoginResponse {
  user: User
}

export interface LogoutResponse {
  loggedOut: boolean
}

export function login(data: LoginPayload) {
  return request.post<LoginResponse>('/auth/login', data)
}

export function logout() {
  return request.post<LogoutResponse>('/auth/logout')
}

export function getMe() {
  return request.get<User>('/auth/me', {
    suppressAuthRedirect: true,
    suppressErrorToast: true
  })
}

export function changePassword(data: ChangePasswordPayload) {
  return request.post<User>('/auth/change-password', data)
}

export function updateProfile(data: UpdateProfilePayload) {
  return request.patch<User>('/auth/profile', data)
}

export function requestPasswordReset(data: PasswordResetRequestPayload) {
  return request.post<PasswordResetRequestResponse>('/auth/password-resets/request', data)
}

export function confirmPasswordReset(data: PasswordResetConfirmPayload) {
  return request.post<User>('/auth/password-resets/confirm', data)
}

export function acceptInvitation(data: AcceptInvitationPayload) {
  return request.post<User>('/auth/invitations/accept', data)
}
