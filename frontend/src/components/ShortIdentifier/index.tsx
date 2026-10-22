interface ShortIdentifierProps {
  value: string
}

export default function ShortIdentifier({ value }: ShortIdentifierProps) {
  const shortValue = value.length > 12 ? `${value.slice(0, 8)}...${value.slice(-4)}` : value

  return shortValue === value ? <span>{value}</span> : <Tooltip title={value}>{shortValue}</Tooltip>
}
import { Tooltip } from 'antd'
