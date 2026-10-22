import { type CSSProperties, type FC, useMemo } from 'react'
import { Typography } from 'antd'
import type { TextProps } from 'antd/es/typography/Text'

const { Text } = Typography

export interface EllipsisTextProps extends Omit<TextProps, 'children' | 'ellipsis'> {
  suffixCount?: number
  children: string | number
  tooltip?: boolean | string
}

const EllipsisText: FC<EllipsisTextProps> = ({
  suffixCount = 0,
  children,
  tooltip = true,
  style,
  ...restProps
}) => {
  const text = String(children)
  const mergedStyle = useMemo<CSSProperties>(
    () => ({ display: 'block', maxWidth: '100%', ...style }),
    [style]
  )
  const mergedTooltip = tooltip === true ? text : tooltip
  const shouldUseSuffix = suffixCount > 0 && suffixCount < text.length

  if (shouldUseSuffix) {
    const suffix = text.slice(-suffixCount)

    return (
      <Text {...restProps} style={mergedStyle} ellipsis={{ suffix, tooltip: mergedTooltip }}>
        {text.slice(0, -suffixCount)}
      </Text>
    )
  }

  return (
    <Text {...restProps} style={mergedStyle} ellipsis={{ tooltip: mergedTooltip }}>
      {text}
    </Text>
  )
}

export default EllipsisText
