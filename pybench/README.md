# pybench

A similar tool to apache bench but with builtin graph creation that differentiates errors and successful responses.

## Dependencies

```
pip install -r requirements.txt
```

## Usage

The following example will spawn 10 concurrent workers each making GET requests to `http://localhost/index.html` until 100 total request have been made.
```bash
> pybench.py -g localhost.png -n 100 -c 10 http://localhost/test.html
```

