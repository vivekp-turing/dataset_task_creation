FROM node:26-bookworm-slim

RUN apt-get update \
    && apt-get install -y --no-install-recommends git ca-certificates patch \
    && rm -rf /var/lib/apt/lists/*

WORKDIR /testbed

# Alibaba sample packages the pinned workspace instead of fetching it at build time.
COPY workspace.tar.gz /tmp/workspace.tar.gz
RUN tar -xzf /tmp/workspace.tar.gz -C /testbed \
    && rm /tmp/workspace.tar.gz \
    && git init -q . \
    && git add -A \
    && git -c user.email=t@t -c user.name=t commit -q -m source-baseline --allow-empty

RUN npm install -g pnpm@10.31.0 \
    && pnpm install --frozen-lockfile \
    && pnpm vitest run test/router.test.ts test/find-all.test.ts --reporter=dot

RUN cp -a /testbed /opt/baseline

RUN git -C /testbed add -A \
    && git -C /testbed -c user.email=t@t -c user.name=t commit -q -m baseline --allow-empty

CMD ["bash"]
