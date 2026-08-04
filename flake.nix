{
  description = "Travelling Deck — kinetosis-reduction Decky plugin for Steam Deck";

  inputs.nixpkgs.url = "github:NixOS/nixpkgs/nixos-unstable";

  outputs = { self, nixpkgs }:
    let
      systems = [ "x86_64-linux" "aarch64-linux" ];
      forAllSystems = f: nixpkgs.lib.genAttrs systems (system: f nixpkgs.legacyPackages.${system});
    in
    {
      devShells = forAllSystems (pkgs: {
        default = pkgs.mkShell {
          packages = [ pkgs.python3 pkgs.nodejs ];
        };
      });

      checks = forAllSystems (pkgs: {
        plugin-metadata = pkgs.runCommand "travelling-deck-plugin-checks" {
          nativeBuildInputs = [ pkgs.python3 ];
        } ''
          python3 ${./checks/check_plugin.py} ${self} > "$out"
        '';
      });
    };
}
