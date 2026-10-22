interface StateIllustrationProps {
  kind: 'empty' | 'error' | 'filtered'
}

function StateIllustration({ kind }: StateIllustrationProps) {
  const isError = kind === 'error'
  const outline = isError
    ? 'var(--ant-color-error-border, #a9878b)'
    : 'var(--ant-color-text-quaternary, #bfbfbf)'
  const divider = 'var(--ant-color-border-secondary, #b7cbe0)'
  const muted = 'var(--ant-color-border, #c7d5e4)'
  const accent = isError ? 'var(--ant-color-error, #b95159)' : outline

  return (
    <svg aria-hidden="true" fill="none" viewBox="0 0 72 64">
      <rect
        fill={
          isError
            ? 'var(--ant-color-error-bg, #fff9f9)'
            : 'var(--ant-color-fill-quaternary, #f8fbff)'
        }
        height="46"
        rx="9"
        stroke={outline}
        strokeWidth="2"
        width="54"
        x="7"
        y="5"
      />
      <path d="M8 17H60" stroke={divider} strokeWidth="2" />
      <circle cx="15" cy="11" fill={isError ? 'var(--ant-color-error, #c5646c)' : outline} r="2" />
      <path d="M21 11H31" stroke={outline} strokeLinecap="round" strokeWidth="2" />
      <path d="M17 25H27M33 25H51" stroke={muted} strokeLinecap="round" strokeWidth="2" />
      <rect
        fill="#fff"
        height="11"
        rx="5.5"
        stroke={isError ? '#c8aeb1' : muted}
        strokeDasharray="3 3"
        strokeWidth="1.5"
        width={kind === 'empty' ? '36' : '30'}
        x="16"
        y="32"
      />
      {kind === 'empty' && (
        <path d="M30 37.5H38" stroke={outline} strokeLinecap="round" strokeWidth="1.5" />
      )}
      {kind === 'filtered' && (
        <>
          <circle
            cx="53"
            cy="43"
            fill="var(--ant-color-fill-quaternary, #fafafa)"
            r="8"
            stroke={accent}
            strokeWidth="2"
          />
          <path d="M59 49L64 54" stroke={accent} strokeLinecap="round" strokeWidth="2.5" />
        </>
      )}
      {kind === 'error' && (
        <>
          <circle cx="54" cy="43" fill="#fff5f5" r="9" stroke={accent} strokeWidth="2" />
          <path d="M54 38V44" stroke={accent} strokeLinecap="round" strokeWidth="2" />
          <circle cx="54" cy="47.5" fill={accent} r="1.2" />
        </>
      )}
    </svg>
  )
}

export default StateIllustration
