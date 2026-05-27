# Vue 3 + Vite

This template should help get you started developing with Vue 3 in Vite. The template uses Vue 3 `<script setup>` SFCs, check out the [script setup docs](https://v3.vuejs.org/api/sfc-script-setup.html#sfc-script-setup) to learn more.

Learn more about IDE Support for Vue in the [Vue Docs Scaling up Guide](https://vuejs.org/guide/scaling-up/tooling.html#ide-support).

## Using Docker for development

### Start the container

Installs dependencies and runs a dev server at `localhost:5173`.

```sh
docker compose --profile dev up
```

### Stop the container

Press `Ctrl + C` in the terminal where `docker compose up` is running, or

```sh
docker compose down
```

### Run commands

Connect to the shell:

```sh
docker compose exec -it frontend-dev sh
```

Or run commands from outside the container:

```sh
docker compose exec frontend-dev <command>
```
