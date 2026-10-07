import { useI18n } from 'vue-i18n'
import { formatTokens } from '../format'

const UNIT_KEYS = ['thousand', 'million', 'billion', 'trillion', 'quadrillion']

/** Token counts in short form with the units of the language chosen (see formatTokens). */
export function useTokenFormat(): (tokens: number) => string {
  const { t, locale } = useI18n()
  return (tokens) =>
    formatTokens(
      tokens,
      UNIT_KEYS.map((key) => t(`tokens.${key}`)),
      locale.value,
    )
}
