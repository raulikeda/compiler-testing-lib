# DrawGrammar (https://github.com/jacquev6/DrawGrammar) command-line tool.
# See README.md in this directory for why it is built this way and how to use it.
FROM docker.io/ocaml/opam:debian-12-ocaml-4.07
USER root
RUN apt-get update && apt-get install -y --no-install-recommends \
        libcairo2-dev pkg-config libgmp-dev fonts-dejavu fontconfig git ca-certificates \
    && rm -rf /var/lib/apt/lists/*
USER opam
RUN opam repo add archive https://github.com/ocaml/opam-repository-archive.git \
    && opam update \
    && opam install -y DrawGrammar.0.2.2 \
    && opam clean -a
WORKDIR /work
ENTRYPOINT ["opam", "exec", "--", "draw_grammar"]
