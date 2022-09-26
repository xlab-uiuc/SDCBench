#Build docker image of centipede/silifuzz build artifacts

## Setup

```
./setup_runner_docker_builder.sh
```

## Run

```
sudo docker run -v $PWD:/app sdc_bench
```

## Run interactive
```
sudo docker run --rm -it --entrypoint bash -v $PWD:/app sdc_bench
```

