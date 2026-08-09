() => {
    const reduceMotion = window.matchMedia("(prefers-reduced-motion: reduce)").matches;
    if (reduceMotion) return;

    let attempts = 0;
    const start = () => {
        attempts += 1;
        const shell = document.querySelector("#studio-shell");
        if (!shell || !window.gsap) {
            if (attempts < 80) window.setTimeout(start, 100);
            return;
        }
        if (shell.dataset.motionReady === "true") return;
        shell.dataset.motionReady = "true";

        const gsap = window.gsap;
        if (window.ScrollTrigger) gsap.registerPlugin(window.ScrollTrigger);

        gsap.from(".studio-nav > *", {
            y: -10,
            opacity: 0,
            duration: 0.55,
            stagger: 0.08,
            ease: "power3.out",
        });
        gsap.from(".studio-titlebar h1", {
            y: 24,
            opacity: 0,
            duration: 0.7,
            ease: "power3.out",
        });
        gsap.from(".media-cell", {
            y: 34,
            opacity: 0,
            scale: 0.985,
            duration: 0.78,
            stagger: 0.12,
            ease: "power3.out",
            delay: 0.12,
        });
        gsap.from(".control-surface > *", {
            y: 22,
            opacity: 0,
            duration: 0.62,
            stagger: 0.08,
            ease: "power2.out",
            delay: 0.28,
        });
        gsap.from(".action-bar", {
            y: 20,
            opacity: 0,
            duration: 0.62,
            ease: "power2.out",
            delay: 0.42,
        });

        if (window.ScrollTrigger && window.innerWidth <= 700) {
            window.ScrollTrigger.create({
                trigger: "#studio-shell",
                start: "top top",
                end: "bottom bottom",
                pin: ".studio-nav",
                pinSpacing: false,
            });
        }
    };

    start();
}
