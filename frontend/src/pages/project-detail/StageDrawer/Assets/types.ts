import type { UploadFile } from 'antd'

export type AssetsView = 'upload' | 'git'

export interface UploadValues {
  file: UploadFile[]
}
