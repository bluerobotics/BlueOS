# The three assets commonwealth's use_local_docs_assets() mounts at
# /usr/blueos/static. Without them every service's /docs page loads them from a
# CDN, which a vehicle without internet cannot reach.
#
# Fetched from the published npm packages rather than the CDN paths upstream's
# bootstrap script curls, so each file is covered by the package's own integrity.
{
  fetchzip,
  runCommand,
}:
let
  swagger-ui-dist = fetchzip {
    url = "https://registry.npmjs.org/swagger-ui-dist/-/swagger-ui-dist-5.34.0.tgz";
    hash = "sha256-e9+bGhp5jkER3n6Co+e5fCox+DMa+8dBCqLxLJyycVA=";
  };

  redoc = fetchzip {
    url = "https://registry.npmjs.org/redoc/-/redoc-2.5.4.tgz";
    hash = "sha256-W2+gCgwH+S0cKzLiThmfZAPoXRuVAmKyFVWJE4AM0WA=";
  };
in
runCommand "blueos-swagger-ui"
  {
    meta = {
      description = "Self-hosted Swagger UI and Redoc assets for BlueOS service docs";
      homepage = "https://github.com/bluerobotics/BlueOS";
    };
  }
  ''
    mkdir -p $out
    install -m644 ${swagger-ui-dist}/swagger-ui-bundle.js $out/swagger-ui-bundle.js
    install -m644 ${swagger-ui-dist}/swagger-ui.css $out/swagger-ui.css
    install -m644 ${redoc}/bundles/redoc.standalone.js $out/redoc.standalone.js
  ''
