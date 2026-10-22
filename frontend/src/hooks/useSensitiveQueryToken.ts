import { useEffect, useState } from 'react'
import { useSearchParams } from 'react-router'

export function useSensitiveQueryToken(parameter = 'token') {
  const [searchParams, setSearchParams] = useSearchParams()
  const incoming = searchParams.get(parameter)
  const [captured, setCaptured] = useState({ parameter, token: incoming })
  const token = incoming ?? (captured.parameter === parameter ? captured.token : null)
  if (incoming && (captured.parameter !== parameter || captured.token !== incoming)) {
    setCaptured({ parameter, token: incoming })
  }
  useEffect(() => {
    if (!incoming) return
    const sanitized = new URLSearchParams(searchParams)
    sanitized.delete(parameter)
    setSearchParams(sanitized, { replace: true })
  }, [incoming, parameter, searchParams, setSearchParams])
  return token
}
