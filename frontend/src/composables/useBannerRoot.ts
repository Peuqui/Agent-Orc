import { inject, type InjectionKey, type Ref } from 'vue'

// The stack of cards at the top of the page (ApprovalBanner): a press in one of its cards is no
// press beside the banner, so it folds none of the others (useDismiss).
export const BANNER_ROOT: InjectionKey<Readonly<Ref<HTMLElement | undefined>>> = Symbol('banner root')

export function useBannerRoot(): Readonly<Ref<HTMLElement | undefined>> {
  const root = inject(BANNER_ROOT)
  if (root === undefined) throw new Error('a banner card is used outside ApprovalBanner')
  return root
}
