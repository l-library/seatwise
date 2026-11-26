import { expect, test } from 'vitest'
import { clearSession, writeSession } from '../auth/session'
import { requireSession } from './router'

test('无会话时守卫抛出 redirect 到 /login', () => {
  clearSession()
  let thrown: unknown
  try {
    requireSession()
  } catch (error) {
    thrown = error
  }
  expect(thrown).toBeInstanceOf(Response)
  expect((thrown as Response).status).toBe(302)
  expect((thrown as Response).headers.get('location')).toBe('/login')
})

test('有会话时守卫不抛出', () => {
  writeSession('ADMIN')
  expect(() => requireSession()).not.toThrow()
  clearSession()
})
