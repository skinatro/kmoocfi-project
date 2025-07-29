k3d cluster create -p 8080:30080@agent:0 -p 5000:80@loadbalancer --agents 2

docker build -f Dockerfile.app -t skinatro/todo-app .
docker push skinatro/todo-app

docker build -f Dockerfile.back -t skinatro/todo-app-back .
docker push skinatro/todo-app-back

kubectl apply -f manifests
kubectl apply -f volume

kubectl rollout restart deployment todo-app-depl 
kubectl rollout restart deployment todo-app-backend-depl 
