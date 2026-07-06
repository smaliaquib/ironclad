FROM golang:1.25-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY *.go ./
RUN CGO_ENABLED=0 go build -o /ai-gateway .

FROM gcr.io/distroless/static-debian12
COPY --from=build /ai-gateway /ai-gateway
EXPOSE 8080
ENTRYPOINT ["/ai-gateway"]
