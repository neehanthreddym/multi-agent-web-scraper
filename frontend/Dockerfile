FROM docker.io/library/node:22-bookworm-slim AS development
RUN npm install --global npm@11.6.0
WORKDIR /app
RUN chown node:node /app
USER node
COPY --chown=node:node package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY --chown=node:node . .
EXPOSE 5173
CMD ["npm", "run", "dev"]

FROM mcr.microsoft.com/playwright:v1.64.0-noble AS browser-tests
RUN npm install --global npm@11.6.0
WORKDIR /app
RUN chown pwuser:pwuser /app
USER pwuser
COPY --chown=pwuser:pwuser package*.json ./
RUN if [ -f package-lock.json ]; then npm ci; else npm install; fi
COPY --chown=pwuser:pwuser . .
CMD ["npm", "run", "test:e2e"]
