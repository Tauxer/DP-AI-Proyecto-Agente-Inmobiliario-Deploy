## Paso 0: Autenticarse en Docker Hub
docker login

## Paso 1: Construir la imagen para linux/amd64 y subirla
# -f Dockerfile.prod es obligatorio: en esta carpeta no hay un "Dockerfile" a secas,
# hay Dockerfile.prod (producción) y Dockerfile.dev (devcontainer).
# --platform linux/amd64 es obligatorio si construyes desde un Mac con chip Apple:
# el build nativo sale arm64 y no arranca en un droplet x86.

docker buildx build \
  --platform linux/amd64 \
  -f Dockerfile.prod \
  -t kevininofuentecolque/app-langchain-inmobiliaria-backend:latest \
  --push \
  .

## Paso 2: Ejecutar en el droplet (el servicio escucha en el puerto 4000)
docker run -d --restart unless-stopped \
  -p 4000:4000 \
  --name agente-inmobiliaria \
  kevininofuentecolque/app-langchain-inmobiliaria-backend:latest

## Paso 3: Comprobar que levantó
curl http://localhost:4000/health
