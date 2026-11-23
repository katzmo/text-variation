# Prototype Tool for Visualizing Textual Variations

## Version 0.2

This implements very basic functionality for uploading and aligning TEI files.

Segments are currently identified by the tags 'head, p, lg, list'. They are grouped by similarity
based on the longest common word subsequence, with a default threshold of 0.4.

To skip the automatic matching, a 'group-id=<id>' attribute can be set on grouped segments.

Background colors indicate the average similarity to all other segments in the group as a gradient
from bright yellow (most similar) to dark red (least similar). Hovering over a segment highlights
all segments in the group, a click aligns the text on the group.

Hold CTRL or CMD and use the up and down arrows or the mouse wheel to zoom in and out of the text.

## Recommended IDE Setup

[VS Code](https://code.visualstudio.com/) + [Vue (Official)](https://marketplace.visualstudio.com/items?itemName=Vue.volar) (and disable Vetur).

## Recommended Browser Setup

- Chromium-based browsers (Chrome, Edge, Brave, etc.):
  - [Vue.js devtools](https://chromewebstore.google.com/detail/vuejs-devtools/nhdogjmejiglipccpnnnanhbledajbpd)
  - [Turn on Custom Object Formatter in Chrome DevTools](http://bit.ly/object-formatters)
- Firefox:
  - [Vue.js devtools](https://addons.mozilla.org/en-US/firefox/addon/vue-js-devtools/)
  - [Turn on Custom Object Formatter in Firefox DevTools](https://fxdx.dev/firefox-devtools-custom-object-formatters/)

## Customize configuration

See [Vite Configuration Reference](https://vite.dev/config/).

## Project Setup

```sh
npm install
```

### Compile and Hot-Reload for Development

```sh
npm run dev
```

### Compile and Minify for Production

```sh
npm run build
```

### Run Tests with [Vitest](https://vitest.dev/)

```sh
npm run test
```

### Lint with [Oxlint](https://oxc.rs)

```sh
npm run lint
```

### Format with [Oxfmt](https://oxc.rs)

```sh
npm run format
```

## Use with Docker

### Start the container

Installs dependencies and runs a dev server at `localhost:5173`.

```sh
docker compose up
```

### Stop the container

Press `Ctrl + C` in the terminal where `docker compose up` is running, or

```sh
docker compose down
```

### Run commands

Connect to the shell:

```sh
docker compose exec -it vue-app sh
```

Or run commands from outside the container:

```sh
docker compose exec vue-app <command>
```
