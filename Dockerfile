FROM golang:1.25-alpine AS build
WORKDIR /src
COPY go.mod go.sum ./
RUN go mod download
COPY *.go openapi.yaml ./
RUN CGO_ENABLED=0 go build -o /mcp-gateway .

FROM gcr.io/distroless/static-debian12
COPY --from=build /mcp-gateway /mcp-gateway
EXPOSE 9000
ENTRYPOINT ["/mcp-gateway"]
