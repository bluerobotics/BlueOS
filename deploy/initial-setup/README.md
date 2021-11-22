# How to run:

1. Build it: `docker build -t kernel .`
2. Create a temporary folder: `mkdir build_image && cd build_image`
3. Run it: `docker run --privileged --cap-add=ALL -v /dev:/dev -v $PWD:/tmp/run -it kernel`

In the end you should see an `*-navigator.img` file that should work on your raspberry.