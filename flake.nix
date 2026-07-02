{
  description = "PaStA - Patch Stack Analysis";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-26.05";

  outputs = { self, nixpkgs }:
    let
      system = "x86_64-linux";
      pkgs = nixpkgs.legacyPackages.${system};

      # flask-nav is not in nixpkgs; patch away Python 3.10+ incompatibility
      # (collections.MutableMapping moved to collections.abc)
      flask-nav = pkgs.python3Packages.buildPythonPackage rec {
        pname = "flask-nav";
        version = "0.6";
        pyproject = true;
        src = pkgs.fetchurl {
          url = "https://files.pythonhosted.org/packages/source/f/flask-nav/flask-nav-${version}.tar.gz";
          sha256 = "1x1k188jxjisdgrspnnw9p4s4ng29lbzk8i1nn5fd8c0adshpr24";
        };
        build-system = [ pkgs.python3Packages.setuptools ];
        postPatch = ''
          substituteInPlace flask_nav/__init__.py \
            --replace-fail "collections.MutableMapping" "collections.abc.MutableMapping"
        '';
        propagatedBuildInputs = with pkgs.python3Packages; [ flask visitor dominate ];
        doCheck = false;
      };

      pythonEnv = pkgs.python3.withPackages (ps: with ps; [
        # mail thread representation (MailCharacteristics, pasta_prepare_evaluation)
        anytree

        # date parsing for mail headers (Util.py)
        dateparser

        # fuzzy patch similarity scoring (PatchEvaluation.py, pasta_check_mbox)
        fuzzywuzzy
        levenshtein

        # git repository access: pygit2 for low-level, gitpython for pasta_patch_descriptions
        pygit2
        gitpython

        # maintainer graph analysis (MAINTAINERS.py, pasta_maintainers_stats)
        networkx

        # cluster quality metrics (pasta_compare_clusters)
        scikit-learn

        # project configuration parsing (Config.py)
        toml

        # progress bars (MAINTAINERS.py, pasta_upstream_duration)
        tqdm

        # HTTP requests for patchwork/mbox fetching (Mbox.py)
        requests

        # web interface (pasta_web)
        flask
        flask-bootstrap
        flask-wtf
        flask-nav

        # interactive development
        ipython
      ]);

      rEnv = pkgs.rWrapper.override {
        packages = with pkgs.rPackages; [
          # analyses/*.R scripts for patch statistics and visualisation
          assertthat
          dplyr
          ggplot2
          ggraph
          igraph
          lubridate
          RColorBrewer
          reshape2
          tikzDevice
        ];
      };

    in
    {
      devShells.${system}.default = pkgs.mkShell {
        packages = with pkgs; [
          pythonEnv
          rEnv

          # version control
          git

          # filterdiff: convert context diffs to unified (Repository/Patch.py)
          patchutils

          # formail: split mbox files for mailbox processing (process_mailbox_maildir.sh)
          procmail

          # get_maintainer.pl is a perl script from the Linux kernel tree
          perl

          # interactive pager for pasta rate/show_cluster (Util.py)
          less

          # live process inspection and profiling
          py-spy

          (pkgs.texliveBasic.withPackages (ps: with ps; [
            biblatex
            biblatex-ieee
            collection-publishers
            latexmk
            collection-latexextra
          ]))
        ];

        shellHook = ''
          export PYTHONPATH="${self}:$PYTHONPATH"
        '';
      };
    };
}
