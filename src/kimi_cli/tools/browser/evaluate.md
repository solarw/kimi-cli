Execute JavaScript code on the current page.

Use this to:
- Extract full HTML: `return document.documentElement.outerHTML`
- Query DOM: `return document.querySelectorAll('input').map(e => e.name)`
- Get localStorage: `return JSON.stringify(localStorage)`
- Scroll to element: `document.querySelector('#id').scrollIntoView()`
- Extract data attributes: `return Array.from(document.querySelectorAll('[data-*]')).map(e => e.dataset)`
- Check network activity (if intercepting): access performance entries

The script runs in the page context. Use `return` to get a result back.
