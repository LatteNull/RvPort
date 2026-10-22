import { type ReactNode, useEffect, useState } from 'react'

import { TableViewStateActiveContext, TableViewStateContext } from './TableViewStateContext'

export default function TableViewStateProvider({
  active = true,
  children
}: {
  active?: boolean
  children: ReactNode
}) {
  const [entries] = useState(() => new Map<string, unknown>())
  useEffect(() => {
    if (!active) entries.clear()
  }, [active, entries])
  return (
    <TableViewStateActiveContext.Provider value={active}>
      <TableViewStateContext.Provider value={active ? entries : undefined}>
        {children}
      </TableViewStateContext.Provider>
    </TableViewStateActiveContext.Provider>
  )
}
