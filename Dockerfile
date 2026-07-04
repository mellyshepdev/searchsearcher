FROM node:22-alpine

WORKDIR /app

COPY package.json ./
RUN npm install

COPY . .

ENV DATABASE_URL=postgresql://placeholder:placeholder@localhost:5432/placeholder
RUN npm run build

EXPOSE 3000

CMD ["sh", "-c", "npx drizzle-kit push --config=drizzle.config.ts --force && npm run start"]
