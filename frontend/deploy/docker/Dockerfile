ARG NODE_IMAGE=node:22.23.2-alpine
ARG NGINX_IMAGE=nginx:1.27-alpine
FROM ${NODE_IMAGE} AS builder

RUN corepack enable

WORKDIR /app

COPY package.json pnpm-lock.yaml pnpm-workspace.yaml ./
ARG NPM_REGISTRY=https://registry.npmjs.org
RUN --mount=type=cache,id=rvport-frontend-pnpm,target=/pnpm/store \
    pnpm install --frozen-lockfile --registry=${NPM_REGISTRY} --store-dir=/pnpm/store

COPY . .
RUN pnpm build

FROM ${NGINX_IMAGE} AS runner

COPY --from=builder /app/dist /usr/share/nginx/html
COPY deploy/nginx/default.conf.template /etc/nginx/templates/default.conf.template

HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
  CMD wget --quiet --spider http://127.0.0.1/ || exit 1

EXPOSE 80

CMD ["nginx", "-g", "daemon off;"]
