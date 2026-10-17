import { onBeforeUnmount } from 'vue'
import type { Ref } from 'vue'
import gsap from 'gsap'

export function useInterfaceMotion(rootEl: Readonly<Ref<HTMLElement | null>>) {
  let entranceMedia: gsap.MatchMedia | null = null
  let successTween: gsap.core.Tween | null = null

  function animateEntrance(): void {
    if (!rootEl.value) return

    entranceMedia?.revert()
    entranceMedia = gsap.matchMedia()
    entranceMedia.add(
      {
        reduceMotion: '(prefers-reduced-motion: reduce)',
        noReduceMotion: '(prefers-reduced-motion: no-preference)',
      },
      (context) => {
        if (context.conditions?.reduceMotion) {
          gsap.set('.js-entrance', { autoAlpha: 1, y: 0 })
          return
        }

        gsap.from('.js-entrance', {
          y: 14,
          autoAlpha: 0,
          duration: 0.42,
          stagger: 0.045,
          ease: 'power2.out',
          clearProps: 'transform,visibility,opacity',
        })
      },
      rootEl.value,
    )
  }

  function animateSuccessToast(): void {
    const node = rootEl.value?.querySelector('.toast--success')
    if (!node) return

    successTween?.kill()
    if (window.matchMedia('(prefers-reduced-motion: reduce)').matches) {
      gsap.set(node, { scale: 1, autoAlpha: 1 })
      return
    }

    successTween = gsap.fromTo(
      node,
      { scale: 0.98, autoAlpha: 0 },
      { scale: 1, autoAlpha: 1, duration: 0.18, ease: 'power2.out' },
    )
  }

  function cleanup(): void {
    successTween?.kill()
    entranceMedia?.revert()
  }

  onBeforeUnmount(cleanup)

  return {
    animateEntrance,
    animateSuccessToast,
  }
}
