import type { ThemeConfig } from 'antd'

const themeToken = {
  colorPrimary: '#1F70EA',
  colorBorder: 'rgba(224, 224, 224, 0.9333)',
  borderRadius: 4
} as const

export const antdTheme: ThemeConfig = {
  cssVar: { prefix: 'ant' },
  token: {
    colorPrimary: themeToken.colorPrimary,
    colorLink: '#1761C9',
    colorLinkHover: '#1658B5',
    colorLinkActive: '#124A98',
    colorBorder: themeToken.colorBorder,
    borderRadius: themeToken.borderRadius,
    borderRadiusLG: 12,
    borderRadiusSM: 4,
    motionDurationFast: '0.1s',
    motionDurationMid: '0.2s',
    motionDurationSlow: '0.3s',
    // See STYLE_GUIDE.md. Page / panel / section headings use h3 / h4 / h5 tokens.
    fontSize: 14,
    fontSizeSM: 12,
    lineHeight: 22 / 14,
    lineHeightSM: 20 / 12,
    fontSizeHeading1: 32,
    fontSizeHeading2: 24,
    fontSizeHeading3: 20,
    fontSizeHeading4: 18,
    fontSizeHeading5: 16,
    lineHeightHeading1: 40 / 32,
    lineHeightHeading2: 32 / 24,
    lineHeightHeading3: 28 / 20,
    lineHeightHeading4: 24 / 18,
    lineHeightHeading5: 24 / 16,
    fontWeightStrong: 600
  },
  components: {
    Button: {
      fontWeight: 400,
      defaultShadow: 'none',
      primaryShadow: 'none',
      dangerShadow: 'none'
    },
    Card: {
      headerFontSize: 16,
      headerHeight: 48,
      fontWeightStrong: 500
    },
    Form: {
      verticalLabelPadding: '0 0 4px',
      labelFontSize: 12,
      labelColor: '#666666'
    },
    Table: {
      headerBg: '#EDF4FF',
      borderColor: '#E0E0E0',
      headerSplitColor: '#E0E0E0'
    }
  }
}
