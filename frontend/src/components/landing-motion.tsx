"use client";
import { useEffect, useRef, useState } from "react";
import { Icon } from "./ui";

export function LandingMotion() {
  useEffect(() => {
    const preference = window.matchMedia("(prefers-reduced-motion: reduce)");
    const animations: Animation[] = [];
    const observer = new IntersectionObserver((entries) => {
      for (const entry of entries) {
        if (!entry.isIntersecting) continue;
        if (!preference.matches) {
          const delay = Number(entry.target.getAttribute("data-reveal-delay") ?? 0);
          animations.push(entry.target.animate(
            [{ opacity: 0.18, transform: "translateY(22px)" }, { opacity: 1, transform: "translateY(0)" }],
            { duration: 760, delay, easing: "cubic-bezier(0.23,1,0.32,1)" },
          ));
        }
        observer.unobserve(entry.target);
      }
    }, { threshold: 0.12 });

      const heroArt = document.querySelector<HTMLElement>(".hero-art");
      const trustSection = document.querySelector<HTMLElement>(".trust-section");
      const blobs = Array.from(document.querySelectorAll<HTMLElement>(".trust-blob"));
      let frame = 0;

      const clamp = (value: number) => Math.min(1, Math.max(0, value));
      const updateScrollMotion = () => {
        frame = 0;
        if (preference.matches) return;

        if (heroArt) {
          const heroProgress = clamp(window.scrollY / Math.max(heroArt.offsetTop * 0.72, 1));
          heroArt.style.opacity = String(1 - heroProgress * 0.72);
          heroArt.style.transform = `translate3d(0, ${heroProgress * 34}px, 0) scale(${1 - heroProgress * 0.12})`;
        }

        if (trustSection) {
          const sectionProgress = clamp((window.innerHeight - trustSection.getBoundingClientRect().top) / window.innerHeight);
          blobs.forEach((blob, index) => {
            const direction = index === 0 ? -1 : 1;
            const rotation = index === 0 ? 20 : -30;
            blob.style.transform = `translate3d(${direction * sectionProgress * 28}px, ${sectionProgress * 18}px, 0) rotate(${rotation}deg) scale(${0.86 + sectionProgress * 0.14})`;
          });
        }
      };
      const onScroll = () => {
        if (!frame) frame = window.requestAnimationFrame(updateScrollMotion);
      };
      updateScrollMotion();
      window.addEventListener("scroll", onScroll, { passive: true });

    document.querySelectorAll(".reveal").forEach((element) => observer.observe(element));
    const stop = () => { if (preference.matches) animations.forEach((animation) => animation.cancel()); };
    return () => {
      observer.disconnect();
      animations.forEach((a) => a.cancel());
      window.removeEventListener("scroll", onScroll);
      if (frame) window.cancelAnimationFrame(frame);
      preference.removeEventListener("change", stop);
    };
  }, []);
  return null;
}

export function MobileMenu() {
  const [open, setOpen] = useState(false);
  const button = useRef<HTMLButtonElement>(null);
  return <div className="mobile-menu" onKeyDown={(event) => { if (event.key === "Escape") { setOpen(false); button.current?.focus(); } }}>
    <button ref={button} type="button" className="icon-button" aria-label={open ? "Close navigation" : "Open navigation"} aria-expanded={open} aria-controls="mobile-navigation" onClick={() => setOpen(!open)}><Icon name={open ? "close" : "menu"} /></button>
    {open && <nav id="mobile-navigation" aria-label="Mobile navigation"><a href="#how-it-works" onClick={() => setOpen(false)}>How it works</a><a href="#trust" onClick={() => setOpen(false)}>Trust</a><a href="#pipeline" onClick={() => setOpen(false)}>Pipeline</a></nav>}
  </div>;
}
