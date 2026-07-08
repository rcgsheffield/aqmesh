# Changelog

## [0.5.1](https://github.com/rcgsheffield/aqmesh/compare/v0.5.0...v0.5.1) (2026-07-08)


### Bug Fixes

* **ci:** allow manual PyPI publish and unblock release-triggered runs ([#152](https://github.com/rcgsheffield/aqmesh/issues/152)) ([47ad1ff](https://github.com/rcgsheffield/aqmesh/commit/47ad1ffc158a104884cbd7a772752783fc5b5f1e))
* publish client package to PyPI as `aqmesh`, not `aqmesh-client` ([#154](https://github.com/rcgsheffield/aqmesh/issues/154)) ([4552adc](https://github.com/rcgsheffield/aqmesh/commit/4552adc08ccfc4a2b396f3f4d98daf9ac9c406f9))

## [0.5.0](https://github.com/rcgsheffield/aqmesh/compare/v0.4.3...v0.5.0) (2026-07-08)


### Features

* **client:** split aqmesh-client into its own publishable package ([#148](https://github.com/rcgsheffield/aqmesh/issues/148)) ([4ea90f5](https://github.com/rcgsheffield/aqmesh/commit/4ea90f51abef29691c4382df96b4f43aeb14dcfa))

## [0.4.3](https://github.com/rcgsheffield/aqmesh/compare/v0.4.2...v0.4.3) (2026-07-08)


### Bug Fixes

* **ingest:** downgrade fetch failures on hardware-mismatched pods to WARNING ([#138](https://github.com/rcgsheffield/aqmesh/issues/138)) ([79a3923](https://github.com/rcgsheffield/aqmesh/commit/79a3923eb0011c61c37fa4b71c876cb259779996)), closes [#64](https://github.com/rcgsheffield/aqmesh/issues/64)


### Continuous Integration

* pass AQMesh test-API credentials into the pytest job ([#142](https://github.com/rcgsheffield/aqmesh/issues/142)) ([b0dbf72](https://github.com/rcgsheffield/aqmesh/commit/b0dbf727f4b878090b6f8b0793115624e1766385))

## [0.4.2](https://github.com/rcgsheffield/aqmesh/compare/v0.4.1...v0.4.2) (2026-07-08)


### Bug Fixes

* **ci:** sync uv.lock within release-please's own workflow run ([#140](https://github.com/rcgsheffield/aqmesh/issues/140)) ([79b812d](https://github.com/rcgsheffield/aqmesh/commit/79b812dde8d2a4f518edbd1a2b8d11a8180af6e7)), closes [#139](https://github.com/rcgsheffield/aqmesh/issues/139)


### Miscellaneous

* sync uv.lock with aqmesh-pipeline v0.4.1 ([b236b8a](https://github.com/rcgsheffield/aqmesh/commit/b236b8a90d4ba0199989af74d11fdbd3f32c5f43))

## [0.4.1](https://github.com/rcgsheffield/aqmesh/compare/v0.4.0...v0.4.1) (2026-07-07)


### Bug Fixes

* **client:** correct SensorDetail path from double to single slash ([#130](https://github.com/rcgsheffield/aqmesh/issues/130)) ([cca3419](https://github.com/rcgsheffield/aqmesh/commit/cca341905b209e9f667950a44db429f9944565e3))


### Documentation

* **citation:** add Vouriot and Hathway as authors ([1fa2396](https://github.com/rcgsheffield/aqmesh/commit/1fa2396fa217941506d61d5bc8bd75ce75cb9232))


### Miscellaneous

* **deps:** bump https://github.com/astral-sh/uv-pre-commit ([#120](https://github.com/rcgsheffield/aqmesh/issues/120)) ([ca2565d](https://github.com/rcgsheffield/aqmesh/commit/ca2565dc50b3753c74c7ec550258ebca1f6dc4ee))
* sync uv.lock with aqmesh-pipeline v0.4.0 ([0e4683e](https://github.com/rcgsheffield/aqmesh/commit/0e4683e2fa39903b840fce820dc79cb96f93d920))

## [0.4.0](https://github.com/rcgsheffield/aqmesh/compare/v0.3.0...v0.4.0) (2026-07-03)


### Features

* **validate:** add non-blocking raw JSON schema validation step ([#109](https://github.com/rcgsheffield/aqmesh/issues/109)) ([a2c4a44](https://github.com/rcgsheffield/aqmesh/commit/a2c4a4458b0b94b284016c5e9e316c559ad5f7c9))


### Bug Fixes

* **ci:** skip lint/security/test on release-please branches ([#111](https://github.com/rcgsheffield/aqmesh/issues/111)) ([e8ba2c4](https://github.com/rcgsheffield/aqmesh/commit/e8ba2c4a9c480cc9ab357ad5d18a937f59251c68)), closes [#110](https://github.com/rcgsheffield/aqmesh/issues/110)
* **metadata:** isolate SensorDetail failures from asset/location sync ([#117](https://github.com/rcgsheffield/aqmesh/issues/117)) ([fa83681](https://github.com/rcgsheffield/aqmesh/commit/fa8368148df463a1e090852ae0f5e17e46a86b48))


### Documentation

* add accurate URL ([69bcf64](https://github.com/rcgsheffield/aqmesh/commit/69bcf64639385b74f3e2cdf0396fb4c175101fc1))
* Add handy notes ([#115](https://github.com/rcgsheffield/aqmesh/issues/115)) ([a8494f0](https://github.com/rcgsheffield/aqmesh/commit/a8494f021f6175a27a7b7bb67c250425219d3e31))
* **storage:** document raw-file SHA-256 integrity strategy ([#118](https://github.com/rcgsheffield/aqmesh/issues/118)) ([45e26c9](https://github.com/rcgsheffield/aqmesh/commit/45e26c9685c259c53edb7dd5bf0728bbff406827))


### Miscellaneous

* **deps:** bump https://github.com/astral-sh/ruff-pre-commit ([#113](https://github.com/rcgsheffield/aqmesh/issues/113)) ([fd80f83](https://github.com/rcgsheffield/aqmesh/commit/fd80f83b6e63eb16ae1235b0d2625693ef2e87e7))
* **deps:** bump https://github.com/astral-sh/uv-pre-commit ([#112](https://github.com/rcgsheffield/aqmesh/issues/112)) ([5baa6f7](https://github.com/rcgsheffield/aqmesh/commit/5baa6f7c8cecf64f0caec9d2084f8cdf31d3e9d3))

## [0.3.0](https://github.com/rcgsheffield/aqmesh/compare/v0.2.0...v0.3.0) (2026-06-26)


### Features

* **clean:** add metadata sidecar for clean CSVs ([#58](https://github.com/rcgsheffield/aqmesh/issues/58)) ([#85](https://github.com/rcgsheffield/aqmesh/issues/85)) ([ff63feb](https://github.com/rcgsheffield/aqmesh/commit/ff63feb836b6381a605fa7a37d1c8de882c68872))
* **csvw:** generate CSVW descriptor alongside each cleaned CSV ([#105](https://github.com/rcgsheffield/aqmesh/issues/105)) ([44d09c1](https://github.com/rcgsheffield/aqmesh/commit/44d09c196c3d9352f60a44dbf46b8c4bbdc83776))
* implement daily resampling of cleaned sensor data ([#99](https://github.com/rcgsheffield/aqmesh/issues/99)) ([4462b64](https://github.com/rcgsheffield/aqmesh/commit/4462b641ef077e84306db1a5f4192f759c71394b))
* **ingest:** write Frictionless datapackage.yaml to raw store ([#100](https://github.com/rcgsheffield/aqmesh/issues/100)) ([bb9b093](https://github.com/rcgsheffield/aqmesh/commit/bb9b093d2ae5a50cbe5bd16922a4132c74ae0913))
* **pipeline:** add metadata sync step so 404 locations appear in output ([#94](https://github.com/rcgsheffield/aqmesh/issues/94)) ([b2ae596](https://github.com/rcgsheffield/aqmesh/commit/b2ae59687cae4a54c6bc1f2a7f638eb6a62e2680))
* **pipeline:** write README.txt to data root on each run ([#104](https://github.com/rcgsheffield/aqmesh/issues/104)) ([24075b0](https://github.com/rcgsheffield/aqmesh/commit/24075b0e4374df5c0afe26d9b742cc0d121594ea))
* **resample:** add n_readings per-bucket sample count ([#102](https://github.com/rcgsheffield/aqmesh/issues/102)) ([cd76af6](https://github.com/rcgsheffield/aqmesh/commit/cd76af6f4afe01e0947141174a63f1a853126a0a))


### Bug Fixes

* **ci:** skip lock-check on release-please branches ([#98](https://github.com/rcgsheffield/aqmesh/issues/98)) ([2317e96](https://github.com/rcgsheffield/aqmesh/commit/2317e96aaefac9cf055d30a666861d5a21c9d1e5)), closes [#91](https://github.com/rcgsheffield/aqmesh/issues/91)
* emit temperature_c from cleaned output ([#96](https://github.com/rcgsheffield/aqmesh/issues/96)) ([86b30ef](https://github.com/rcgsheffield/aqmesh/commit/86b30ef70dc7b254139162ad744d9f0de3f565d8))
* pin UTC timezone for reading_datestamp ([#82](https://github.com/rcgsheffield/aqmesh/issues/82)) ([#101](https://github.com/rcgsheffield/aqmesh/issues/101)) ([d35dd62](https://github.com/rcgsheffield/aqmesh/commit/d35dd6220037fbbe5e754072ca13c13c1fe50e9f))


### Documentation

* **claude-md:** document CI checks and PR test plan scope ([#103](https://github.com/rcgsheffield/aqmesh/issues/103)) ([5c5644c](https://github.com/rcgsheffield/aqmesh/commit/5c5644c4a0d93edaf1adb16d572d7b079264854b))
* **service-management:** move SSH tunnel section earlier, add ~/.ssh/config instructions ([#95](https://github.com/rcgsheffield/aqmesh/issues/95)) ([4abbb73](https://github.com/rcgsheffield/aqmesh/commit/4abbb736728479754c622cf7538be805c6aca958))

## [0.2.0](https://github.com/rcgsheffield/aqmesh/compare/v0.1.4...v0.2.0) (2026-06-26)


### Features

* add aqmesh repeat command ([#68](https://github.com/rcgsheffield/aqmesh/issues/68)) ([#74](https://github.com/rcgsheffield/aqmesh/issues/74)) ([50449b5](https://github.com/rcgsheffield/aqmesh/commit/50449b53e919b245f93c35a80ced807040eb40fb))
* **cli:** add read-only API context commands and API reference docs ([#84](https://github.com/rcgsheffield/aqmesh/issues/84)) ([b609b0a](https://github.com/rcgsheffield/aqmesh/commit/b609b0acdcd0236889f7c1a2540ce9b75fa6e326))
* **schema:** add JSON schemas and Frictionless Data descriptor for raw data ([#76](https://github.com/rcgsheffield/aqmesh/issues/76)) ([ecb1fa3](https://github.com/rcgsheffield/aqmesh/commit/ecb1fa3568f6e78e708ee536d111a561f2413a11))


### Bug Fixes

* **deploy:** change default data volume mount point to /mnt/aqmesh ([#80](https://github.com/rcgsheffield/aqmesh/issues/80)) ([69ec51a](https://github.com/rcgsheffield/aqmesh/commit/69ec51a08ef20476a00e429abb0e37cedd3c5fff))
* **flows:** diagnostic logging for zero-CSV-output (issue [#55](https://github.com/rcgsheffield/aqmesh/issues/55)) ([#61](https://github.com/rcgsheffield/aqmesh/issues/61)) ([3c1e2cc](https://github.com/rcgsheffield/aqmesh/commit/3c1e2ccdb99400ddd8cd0bbdf51835873479b10a))


### Documentation

* add CLAUDE.md for Claude Code ([#77](https://github.com/rcgsheffield/aqmesh/issues/77)) ([73bc390](https://github.com/rcgsheffield/aqmesh/commit/73bc3903b0523e9bb3bc63cce7128ae077e31c79))
* add missing docstrings to transform and client modules ([#62](https://github.com/rcgsheffield/aqmesh/issues/62)) ([25c55f8](https://github.com/rcgsheffield/aqmesh/commit/25c55f8417c88c07f43b2d0f6454835d19e209ef))
* add pipeline scheduling, state, and backfill explainer ([#71](https://github.com/rcgsheffield/aqmesh/issues/71)) ([5a9180d](https://github.com/rcgsheffield/aqmesh/commit/5a9180d6f0a1c661ce418696c015d085cd676c1a))
* warn against using production credentials in local development ([#72](https://github.com/rcgsheffield/aqmesh/issues/72)) ([ef076e8](https://github.com/rcgsheffield/aqmesh/commit/ef076e8ea4eabc5f5059056f1a3be04df7d27e5c))


### Continuous Integration

* add lychee link check for Markdown docs ([#78](https://github.com/rcgsheffield/aqmesh/issues/78)) ([0ed3e0f](https://github.com/rcgsheffield/aqmesh/commit/0ed3e0fafc23a7e010b8860f7bfa6fc5bdbb5bc5))
* add workflow_dispatch to release-to-orda for manual backfill ([#59](https://github.com/rcgsheffield/aqmesh/issues/59)) ([7941f09](https://github.com/rcgsheffield/aqmesh/commit/7941f09933eb5d08cefc5df5bf377e241d4ab3b1))
* lint GitHub Actions workflows with actionlint ([#79](https://github.com/rcgsheffield/aqmesh/issues/79)) ([5d0398e](https://github.com/rcgsheffield/aqmesh/commit/5d0398e5b73540a66fbf666aafab315a3f0ae008))


### Miscellaneous

* **deps:** bump pydantic-settings in the uv group across 1 directory ([#87](https://github.com/rcgsheffield/aqmesh/issues/87)) ([506cb98](https://github.com/rcgsheffield/aqmesh/commit/506cb98d7e63e6790d679f996890b5e7cd867305))

## [0.1.4](https://github.com/rcgsheffield/aqmesh/compare/v0.1.3...v0.1.4) (2026-06-19)


### Bug Fixes

* **deps:** sync uv.lock with pyproject 0.1.3 ([#47](https://github.com/rcgsheffield/aqmesh/issues/47)) ([fe9b0d1](https://github.com/rcgsheffield/aqmesh/commit/fe9b0d1d1dc30884650f4ab3d2bad38e5a6427eb))


### Documentation

* front-door README and operator index improvements ([#45](https://github.com/rcgsheffield/aqmesh/issues/45)) ([0b56e4e](https://github.com/rcgsheffield/aqmesh/commit/0b56e4e137dba421e3256b9ae8aa27a8dc074c49))


### Continuous Integration

* archive releases to ORDA for citable DOIs ([#44](https://github.com/rcgsheffield/aqmesh/issues/44)) ([1d32c2e](https://github.com/rcgsheffield/aqmesh/commit/1d32c2e643ee1101562cdaa63aa47b332f77732d)), closes [#43](https://github.com/rcgsheffield/aqmesh/issues/43)
* auto-sync uv.lock on release-please branches ([#56](https://github.com/rcgsheffield/aqmesh/issues/56)) ([600117d](https://github.com/rcgsheffield/aqmesh/commit/600117da48ab9fa5caaafb7c900af18416b10f65))


### Miscellaneous

* add pre-commit essentials (ruff, file hygiene, dependabot) ([#48](https://github.com/rcgsheffield/aqmesh/issues/48)) ([4dcff26](https://github.com/rcgsheffield/aqmesh/commit/4dcff2622fb420b601cac330e3ed7fe8f4505ade))
* **ci:** pin runs-on to ubuntu-24.04 ([#54](https://github.com/rcgsheffield/aqmesh/issues/54)) ([9db94eb](https://github.com/rcgsheffield/aqmesh/commit/9db94eb236eefe4a1a88c5839b0c972accfec688)), closes [#52](https://github.com/rcgsheffield/aqmesh/issues/52)
* **deps:** bump https://github.com/astral-sh/ruff-pre-commit ([#49](https://github.com/rcgsheffield/aqmesh/issues/49)) ([cf6dbc8](https://github.com/rcgsheffield/aqmesh/commit/cf6dbc8fcd2ad41346ec42a459833bf3df089ff5))
* **deps:** bump https://github.com/pre-commit/pre-commit-hooks ([#50](https://github.com/rcgsheffield/aqmesh/issues/50)) ([d63dda3](https://github.com/rcgsheffield/aqmesh/commit/d63dda3a56261f0d41e6f4d8b35ccfda2c4ef9ec))

## [0.1.3](https://github.com/rcgsheffield/aqmesh/compare/v0.1.2...v0.1.3) (2026-06-19)


### Bug Fixes

* **deploy:** ensure UTF-8 locale for prefect CLI commands ([29be471](https://github.com/rcgsheffield/aqmesh/commit/29be471658ce72b59d270b300dea196c12a9433f))
* **deploy:** ensure UTF-8 locale for prefect CLI commands ([4be452d](https://github.com/rcgsheffield/aqmesh/commit/4be452d0ba6cce60d48f920b8b97292cd474958e)), closes [#40](https://github.com/rcgsheffield/aqmesh/issues/40)
* **deploy:** use --overwrite when creating Prefect work pool ([a98713c](https://github.com/rcgsheffield/aqmesh/commit/a98713c39038daae4a004adafb3d4e760c60cd10))
* **deploy:** use --overwrite when creating Prefect work pool ([2198062](https://github.com/rcgsheffield/aqmesh/commit/2198062bb5354f743c2fa25e1c31c0dfcd31d4f6)), closes [#34](https://github.com/rcgsheffield/aqmesh/issues/34)
* **deploy:** use en_GB.UTF-8 locale and export at script top ([c9c171b](https://github.com/rcgsheffield/aqmesh/commit/c9c171b1dfeb2c4ca8d8511d6445b38aaeae7834))
* switch to dotted-module entrypoint to fix relative imports ([46d3bec](https://github.com/rcgsheffield/aqmesh/commit/46d3bec1c8011d94f46999591f7859eabdf39561))
* switch to dotted-module entrypoint to fix relative imports ([69d9296](https://github.com/rcgsheffield/aqmesh/commit/69d92962920e798d9e47850731acc99ac47700ee)), closes [#33](https://github.com/rcgsheffield/aqmesh/issues/33)


### Documentation

* document systemctl edit drop-ins for operator overrides ([cb99d68](https://github.com/rcgsheffield/aqmesh/commit/cb99d689c498e9f33002529f32bec2274beb58f9))
* document systemctl edit drop-ins for operator overrides ([b1b02e1](https://github.com/rcgsheffield/aqmesh/commit/b1b02e150270be4da44ba0253d75183e44ab05f2)), closes [#32](https://github.com/rcgsheffield/aqmesh/issues/32)


### Continuous Integration

* catch uv.lock / pyproject.toml drift before CI ([#38](https://github.com/rcgsheffield/aqmesh/issues/38)) ([254171d](https://github.com/rcgsheffield/aqmesh/commit/254171d212099a2e6187f91f9b35b92721938a21))
* catch uv.lock / pyproject.toml drift before CI ([#38](https://github.com/rcgsheffield/aqmesh/issues/38)) ([1568eaf](https://github.com/rcgsheffield/aqmesh/commit/1568eafbe8f61c4e513adb342ec85af9b8be0851))

## [0.1.2](https://github.com/rcgsheffield/aqmesh/compare/v0.1.1...v0.1.2) (2026-06-19)


### Bug Fixes

* **client:** drop trailing version segment from LocationData/Next path ([403928d](https://github.com/rcgsheffield/aqmesh/commit/403928df0660111be3c1a163c5ac9e50054f0e13))
* **client:** drop trailing version segment from LocationData/Next path ([470d1ba](https://github.com/rcgsheffield/aqmesh/commit/470d1ba3e909749893f710d441633d5011f5e8f7)), closes [#8](https://github.com/rcgsheffield/aqmesh/issues/8)
* **deploy:** reduce Prefect SQLite lock contention ([#16](https://github.com/rcgsheffield/aqmesh/issues/16)) ([9edb97b](https://github.com/rcgsheffield/aqmesh/commit/9edb97bdfb6eca3d5a11baf586fe3b419ae8a377))
* **deploy:** reduce Prefect SQLite lock contention ([#16](https://github.com/rcgsheffield/aqmesh/issues/16)) ([2516282](https://github.com/rcgsheffield/aqmesh/commit/2516282466485584f9d64ea03877a74eac5c8554))
* **deploy:** suppress interactive Prefect prompt during deploy ([6a464f0](https://github.com/rcgsheffield/aqmesh/commit/6a464f0b6a57ada018b2f176b7d41f9629358ca9))
* **deploy:** suppress interactive Prefect prompt during deploy ([f38f128](https://github.com/rcgsheffield/aqmesh/commit/f38f12830be9497c88f5b2a7d541def9c456c2be)), closes [#4](https://github.com/rcgsheffield/aqmesh/issues/4)
* **ingest:** isolate per-param API failures so one param's 500 doesn't abort the run ([cbac5a2](https://github.com/rcgsheffield/aqmesh/commit/cbac5a2aa7752a1a96cddf6dfa361809caa5a348))
* **ingest:** isolate per-param API failures so one param's 500 doesn't abort the run ([fab6105](https://github.com/rcgsheffield/aqmesh/commit/fab6105be908dc96dd513b4b10cb41763bf21261))
* suppress HashError on ingest_location_param by setting cache_policy=NO_CACHE ([f548c9c](https://github.com/rcgsheffield/aqmesh/commit/f548c9c8c296a2b31d1dddf9e5f77202667a3e6d))
* suppress HashError on ingest_location_param by setting cache_policy=NO_CACHE ([946c672](https://github.com/rcgsheffield/aqmesh/commit/946c6729a5dad466ed989c92d19d52456e387468)), closes [#10](https://github.com/rcgsheffield/aqmesh/issues/10)
* **test:** align new gas-fail test with no-trailing-version URL format ([989ec1f](https://github.com/rcgsheffield/aqmesh/commit/989ec1fae0de8bd1aa846be3110dcaad715a7fe9))


### Documentation

* add Prefect web UI guide ([a0866de](https://github.com/rcgsheffield/aqmesh/commit/a0866deeabeac093580428e199b08b579f112d05))
* add service-management.md operator quick-reference ([0b9dd6a](https://github.com/rcgsheffield/aqmesh/commit/0b9dd6a41aa33dfc064a462b47ad7bad573f95a8))
* add service-management.md operator quick-reference ([c24daeb](https://github.com/rcgsheffield/aqmesh/commit/c24daeb18ab9dc089aece49009291f8fe3f19c21)), closes [#14](https://github.com/rcgsheffield/aqmesh/issues/14)
* document release process in RELEASING.md ([49ecd1f](https://github.com/rcgsheffield/aqmesh/commit/49ecd1f42d7f1b993399cf3a53cf766650f48f76))
* document release process in RELEASING.md ([0c0934c](https://github.com/rcgsheffield/aqmesh/commit/0c0934cc85b65b3c114b732fd2b3f9b7a891a539))
* extract deployment guide into docs/deployment.md ([05bf626](https://github.com/rcgsheffield/aqmesh/commit/05bf626d15d0b1269b24625c552b4c4d86ecd9d3))
* Note hardware needs ([9005933](https://github.com/rcgsheffield/aqmesh/commit/9005933bc0fdd6ecd71ab5809c93a8a1e608be91))


### Continuous Integration

* add pip-audit and bandit security scanning ([e38941b](https://github.com/rcgsheffield/aqmesh/commit/e38941b1d935cfe4340cdf0eb5b9a5a24e18ab96))
* add pip-audit and bandit security scanning ([#17](https://github.com/rcgsheffield/aqmesh/issues/17)) ([562c585](https://github.com/rcgsheffield/aqmesh/commit/562c5856fddb618890b3b0d3e7850a6c6d6f4041))
* add release-please for automated release management ([48922ee](https://github.com/rcgsheffield/aqmesh/commit/48922eeda328d4a190bbb34c02855034b684e75a))
* add release-please for automated release management ([b48b8b2](https://github.com/rcgsheffield/aqmesh/commit/b48b8b2f655744bd8717828ff5985482480c65d9)), closes [#18](https://github.com/rcgsheffield/aqmesh/issues/18)
* lint shell scripts with ShellCheck ([2eb5978](https://github.com/rcgsheffield/aqmesh/commit/2eb5978a82bca719d9bd44dc869dccab237befaf))
* lint shell scripts with ShellCheck ([0c6ddd9](https://github.com/rcgsheffield/aqmesh/commit/0c6ddd99cd1f16b3260542019617e5e2a1f6e578))
* split workflow and add paths filters ([71cec0b](https://github.com/rcgsheffield/aqmesh/commit/71cec0b1f43c7d6f32f27b392c4fac7a06a17663))
* split workflow and add paths filters ([#20](https://github.com/rcgsheffield/aqmesh/issues/20)) ([4c90358](https://github.com/rcgsheffield/aqmesh/commit/4c9035872d11459fd10db0646f5cd947c711ba6c))


### Tests

* expand suite to full coverage and enforce 90% floor ([cf4f879](https://github.com/rcgsheffield/aqmesh/commit/cf4f879c5327c1b1e98fb81223cc067b2e33fbb4))


### Miscellaneous

* CI status badge ([d8bfd50](https://github.com/rcgsheffield/aqmesh/commit/d8bfd509c577a0ce32bfa0685cadee9c893e8094))
* **deps:** bump cryptography from 48.0.0 to 48.0.1 in the uv group across 1 directory ([4ccdfde](https://github.com/rcgsheffield/aqmesh/commit/4ccdfdefbf587cc2251b8b77ac2fa9e0de022afc))
* **deps:** bump cryptography in the uv group across 1 directory ([492544e](https://github.com/rcgsheffield/aqmesh/commit/492544e97bacf08e31a16d1479cab41fd695a31b))
* **deps:** bump starlette from 1.2.1 to 1.3.1 in the uv group across 1 directory ([8fdc8a3](https://github.com/rcgsheffield/aqmesh/commit/8fdc8a36a4b27698129950f883ae26d86135a4a4))
* **deps:** bump starlette in the uv group across 1 directory ([ee2a6da](https://github.com/rcgsheffield/aqmesh/commit/ee2a6da770f3e58d13d3da14982b01c755dd7c6e))
* drop component prefix from release tags ([61cddb3](https://github.com/rcgsheffield/aqmesh/commit/61cddb3ff4f9300e3e2828be32adcf857940f34f))
* drop component prefix from release tags ([fd460d5](https://github.com/rcgsheffield/aqmesh/commit/fd460d5a8e67c78fbbeafe814fdf6092cfc583eb))
* fix CI action version ([de5b908](https://github.com/rcgsheffield/aqmesh/commit/de5b908d3e5e8295984bf3f7cddd4a0dff820c7f))
* **main:** release aqmesh-pipeline 0.1.1 ([a41008a](https://github.com/rcgsheffield/aqmesh/commit/a41008a14aa834a969c7bb6b661ee2d927b4e1bb))
* **main:** release aqmesh-pipeline 0.1.1 ([ae56730](https://github.com/rcgsheffield/aqmesh/commit/ae567307713539b54eb92bc804df0adae4eb95aa))
* sync uv.lock with aqmesh-pipeline 0.1.1 ([689361f](https://github.com/rcgsheffield/aqmesh/commit/689361f1a891bedae72faa9345ac56f109993b66))
* sync uv.lock with aqmesh-pipeline 0.1.1 ([49a265e](https://github.com/rcgsheffield/aqmesh/commit/49a265e829c116af26bcdd34c9d42a7194a5721f))

## [0.1.1](https://github.com/rcgsheffield/aqmesh/compare/aqmesh-pipeline-v0.1.0...aqmesh-pipeline-v0.1.1) (2026-06-19)


### Bug Fixes

* **deploy:** reduce Prefect SQLite lock contention ([#16](https://github.com/rcgsheffield/aqmesh/issues/16)) ([9edb97b](https://github.com/rcgsheffield/aqmesh/commit/9edb97bdfb6eca3d5a11baf586fe3b419ae8a377))
* **deploy:** reduce Prefect SQLite lock contention ([#16](https://github.com/rcgsheffield/aqmesh/issues/16)) ([2516282](https://github.com/rcgsheffield/aqmesh/commit/2516282466485584f9d64ea03877a74eac5c8554))
* **deploy:** suppress interactive Prefect prompt during deploy ([6a464f0](https://github.com/rcgsheffield/aqmesh/commit/6a464f0b6a57ada018b2f176b7d41f9629358ca9))
* **deploy:** suppress interactive Prefect prompt during deploy ([f38f128](https://github.com/rcgsheffield/aqmesh/commit/f38f12830be9497c88f5b2a7d541def9c456c2be)), closes [#4](https://github.com/rcgsheffield/aqmesh/issues/4)


### Documentation

* add Prefect web UI guide ([a0866de](https://github.com/rcgsheffield/aqmesh/commit/a0866deeabeac093580428e199b08b579f112d05))
* add service-management.md operator quick-reference ([0b9dd6a](https://github.com/rcgsheffield/aqmesh/commit/0b9dd6a41aa33dfc064a462b47ad7bad573f95a8))
* add service-management.md operator quick-reference ([c24daeb](https://github.com/rcgsheffield/aqmesh/commit/c24daeb18ab9dc089aece49009291f8fe3f19c21)), closes [#14](https://github.com/rcgsheffield/aqmesh/issues/14)
* document release process in RELEASING.md ([49ecd1f](https://github.com/rcgsheffield/aqmesh/commit/49ecd1f42d7f1b993399cf3a53cf766650f48f76))
* document release process in RELEASING.md ([0c0934c](https://github.com/rcgsheffield/aqmesh/commit/0c0934cc85b65b3c114b732fd2b3f9b7a891a539))
* extract deployment guide into docs/deployment.md ([05bf626](https://github.com/rcgsheffield/aqmesh/commit/05bf626d15d0b1269b24625c552b4c4d86ecd9d3))
* Note hardware needs ([9005933](https://github.com/rcgsheffield/aqmesh/commit/9005933bc0fdd6ecd71ab5809c93a8a1e608be91))


### Continuous Integration

* add pip-audit and bandit security scanning ([e38941b](https://github.com/rcgsheffield/aqmesh/commit/e38941b1d935cfe4340cdf0eb5b9a5a24e18ab96))
* add pip-audit and bandit security scanning ([#17](https://github.com/rcgsheffield/aqmesh/issues/17)) ([562c585](https://github.com/rcgsheffield/aqmesh/commit/562c5856fddb618890b3b0d3e7850a6c6d6f4041))
* add release-please for automated release management ([48922ee](https://github.com/rcgsheffield/aqmesh/commit/48922eeda328d4a190bbb34c02855034b684e75a))
* add release-please for automated release management ([b48b8b2](https://github.com/rcgsheffield/aqmesh/commit/b48b8b2f655744bd8717828ff5985482480c65d9)), closes [#18](https://github.com/rcgsheffield/aqmesh/issues/18)
* lint shell scripts with ShellCheck ([2eb5978](https://github.com/rcgsheffield/aqmesh/commit/2eb5978a82bca719d9bd44dc869dccab237befaf))
* lint shell scripts with ShellCheck ([0c6ddd9](https://github.com/rcgsheffield/aqmesh/commit/0c6ddd99cd1f16b3260542019617e5e2a1f6e578))


### Tests

* expand suite to full coverage and enforce 90% floor ([cf4f879](https://github.com/rcgsheffield/aqmesh/commit/cf4f879c5327c1b1e98fb81223cc067b2e33fbb4))


### Miscellaneous

* CI status badge ([d8bfd50](https://github.com/rcgsheffield/aqmesh/commit/d8bfd509c577a0ce32bfa0685cadee9c893e8094))
* **deps:** bump cryptography from 48.0.0 to 48.0.1 in the uv group across 1 directory ([4ccdfde](https://github.com/rcgsheffield/aqmesh/commit/4ccdfdefbf587cc2251b8b77ac2fa9e0de022afc))
* **deps:** bump cryptography in the uv group across 1 directory ([492544e](https://github.com/rcgsheffield/aqmesh/commit/492544e97bacf08e31a16d1479cab41fd695a31b))
* **deps:** bump starlette from 1.2.1 to 1.3.1 in the uv group across 1 directory ([8fdc8a3](https://github.com/rcgsheffield/aqmesh/commit/8fdc8a36a4b27698129950f883ae26d86135a4a4))
* **deps:** bump starlette in the uv group across 1 directory ([ee2a6da](https://github.com/rcgsheffield/aqmesh/commit/ee2a6da770f3e58d13d3da14982b01c755dd7c6e))
* fix CI action version ([de5b908](https://github.com/rcgsheffield/aqmesh/commit/de5b908d3e5e8295984bf3f7cddd4a0dff820c7f))
