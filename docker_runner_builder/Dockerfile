FROM ubuntu:18.04

# This image is for building output artifacts for runner
# sudo docker build --tag sdc_bench .
# sudo docker run sdc_bench -v output:/app
RUN apt-get update && apt-get install -y \
    software-properties-common \
    curl \
    wget

RUN add-apt-repository ppa:ubuntu-toolchain-r/test

RUN apt-get update && apt-get install -y \
    gcc-11 \
    g++-11

RUN update-alternatives --install /usr/bin/gcc gcc /usr/bin/gcc-11 100
RUN update-alternatives --install /usr/bin/g++ g++ /usr/bin/g++-11 100

RUN add-apt-repository ppa:ubuntu-toolchain-r/test
RUN wget -O - https://apt.llvm.org/llvm-snapshot.gpg.key | apt-key add -
RUN echo "deb http://apt.llvm.org/bionic/ llvm-toolchain-bionic-14 main" | tee -a /etc/apt/sources.list

RUN apt-get update && apt-get install -y \
    clang-14 \
    clang++-14 \
    llvm-14 \
    lld-14

RUN update-alternatives --install /usr/bin/clang clang /usr/bin/clang-14 50 --slave /usr/bin/clang++ clang++ /usr/bin/clang++-14
#RUN update-alternatives --install /usr/bin/cc cc /usr/bin/clang 100
#RUN update-alternatives --install /usr/bin/c++ c++ /usr/bin/clang++ 100

RUN apt-get install -y \
    python3 \
    python3-pip

#RUN apt-get upgrade -y \
#    libc6 \
#    libstdc++6

#RUN apt-get dist-upgrade -y

#RUN curl https://github.com/bazelbuild/bazel/releases/download/5.3.1/bazel-5.3.1-installer-linux-x86_64.sh -o bazel-5.3.1-installer-linux-x86_64.sh
#RUN chmod +x bazel-5.3.1-installer-linux-x86_64.sh
#RUN ./bazel-5.3.1-installer-linux-x86_64.sh

RUN echo "deb [arch=amd64] http://storage.googleapis.com/bazel-apt stable jdk1.8" | tee /etc/apt/sources.list.d/bazel.list
RUN curl https://bazel.build/bazel-release.pub.gpg | apt-key add -

RUN apt-get update && apt-get install -y \
    git \
    bazel \
    cmake \
    libssl-dev


RUN git clone https://github.com/abseil/abseil-cpp.git
RUN cd abseil-cpp && mkdir build && cd build && cmake -DCMAKE_INSTALL_PREFIX=/usr -DABSL_BUILD_TESTING=OFF -DABSL_USE_GOOGLETEST_HEAD=ON -DCMAKE_CXX_STANDARD=17 .. && make install -j32

RUN update-alternatives --install /usr/bin/cc cc /usr/bin/clang-14 100
RUN update-alternatives --install /usr/bin/c++ c++ /usr/bin/clang++-14 100
RUN update-alternatives --install /usr/bin/lld lld /usr/bin/lld-14 100

ENV CC=/usr/bin/clang-14
ENV CXX=/usr/bin/clang++-14

WORKDIR /app
#COPY . /app

RUN mkdir -p build

CMD ["sh", "-c", "./setup_runner.sh && cp -rL tools/cpu-check build/cpu-check && cp -rL tools/centipede/ build/centipede && cp -rL tools/silifuzz build/silifuzz"]

