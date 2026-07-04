FROM golang:1.25-alpine AS build
WORKDIR /src
COPY go.mod ./
COPY main.go ./
RUN CGO_ENABLED=0 go build -o /router .

FROM gcr.io/distroless/static-debian12
COPY --from=build /router /router
EXPOSE 8080
ENTRYPOINT ["/router"]
