import { createContext } from 'react'

export type StagePresentation = 'drawer' | 'panel'

export const StagePresentationContext = createContext<StagePresentation>('drawer')
