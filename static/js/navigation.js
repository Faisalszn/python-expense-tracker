(() => {
    const dialog = document.getElementById("navigation-drawer");
    const toggle = document.getElementById("menu-toggle");
    if (!dialog || !toggle || typeof dialog.showModal !== "function") return;
    document.documentElement.classList.add("has-drawer");
    toggle.hidden = false;
    toggle.addEventListener("click", () => {
        dialog.showModal(); // Native modal contains focus and makes the background inert.
        toggle.setAttribute("aria-expanded", "true");
        document.body.classList.add("drawer-open");
        dialog.querySelector("[data-close-drawer]").focus();
    });
    const restoreFocus = () => {
        toggle.setAttribute("aria-expanded", "false");
        document.body.classList.remove("drawer-open");
        if (toggle.getClientRects().length) toggle.focus();
        else document.querySelector(".site-header .nav-brand").focus();
    };
    const closeDrawer = () => {
        dialog.close();
        restoreFocus();
    };
    dialog.querySelector("[data-close-drawer]").addEventListener("click", closeDrawer);
    dialog.addEventListener("click", (event) => {
        const bounds = dialog.getBoundingClientRect();
        if (event.target === dialog && (event.clientX < bounds.left || event.clientX > bounds.right || event.clientY < bounds.top || event.clientY > bounds.bottom)) closeDrawer();
    });
    dialog.addEventListener("close", restoreFocus);
    dialog.addEventListener("cancel", (event) => {
        event.preventDefault();
        closeDrawer();
    });
    dialog.addEventListener("keydown", (event) => {
        if (event.key !== "Tab") return;
        const controls = [...dialog.querySelectorAll("a[href], button:not([disabled])")]
            .filter((element) => element.getClientRects().length);
        const first = controls[0],
            last = controls[controls.length - 1];
        if (event.shiftKey && document.activeElement === first) {
            event.preventDefault();
            last.focus();
        } else if (!event.shiftKey && document.activeElement === last) {
            event.preventDefault();
            first.focus();
        }
    });
    const desktop = window.matchMedia("(min-width: 1024px)");
    desktop.addEventListener("change", () => {
        if (desktop.matches && dialog.open) closeDrawer();
    });
})();
