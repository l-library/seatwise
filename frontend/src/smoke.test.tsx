import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

test('renders React markup in the vitest jsdom environment', () => {
  render(<p>seatwise</p>)
  expect(screen.getByText('seatwise')).toBeTruthy()
})
