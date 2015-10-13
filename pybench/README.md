# pybench

A similar tool to apache bench but with builtin graph creation that differenciates errors and successful responses.

## Dependencies
 - python >= 2.6
 - twisted >= 13.1.0
 - matplotlib >= 1.3.1

## Usage

The following example will spawn 10 concurrent workers each making GET requests to `http://localhost/index.html` until 100 total request have been made.
```bash
> pybench.py -g localhost.png -n 100 -c 10 http://localhost/test.html
```

