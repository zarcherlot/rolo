# Authored Operation Contracts

This document is generated from `src/rolo/operation_contracts/*.yaml`. 
`RELEASED` contracts back built-in operations; `GATEABLE` contracts may be 
implemented and promoted by Adapt. The remaining product vocabulary stays `DRAFT` 
and cannot become `VERIFIED` until an authored contract is added.

Catalog SHA-256: `8408a7e8f7bc49d4121a973148ba6eb4dee1c1c3a1ad232e79259e3f21d65635`

| Operation | Lifecycle | Version | Data | Contract SHA-256 |
|---|---|---|---|---|
| `app.base.status` | GATEABLE | `1.1.0` | `INTERNAL` | `a86e2e8bd0f0cf83df6f4203b5615bcc6a7b51efbc66c443d3c4c664d3cf0e47` |
| `app.calibration.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `79442bd94b62c07fc17589eab66fbc33e3fead8a82f4d8fb04ff004351636233` |
| `app.calibration.list` | GATEABLE | `1.1.0` | `INTERNAL` | `25f5c2e0418fd9834a74100c923f7ebdb39c1b781ab2da9be92162a47fdac9b2` |
| `app.calibration.status` | GATEABLE | `1.1.0` | `INTERNAL` | `9575987f77a34dbb909bb3cf2d08178acedc9c2a87d8bb182a91fecc31bad7e5` |
| `app.calibration.validate` | GATEABLE | `1.1.0` | `SENSITIVE` | `a59aab3bff256f641032ea101eacf189bd22282429c10191c7518c2a122471fc` |
| `app.camera.calibration.status` | GATEABLE | `1.1.0` | `INTERNAL` | `0c02ac3a7894e04315d62b3b3df64a8527e8d60e4d159a1e4567a0631c02d6ad` |
| `app.camera.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `1c089c659d2b9ee0a43f36dd20cf652b29c5b2dff2b5ed56092db38a5ea9747e` |
| `app.camera.list` | GATEABLE | `1.1.0` | `INTERNAL` | `fe823d481b447927b4c38a998efe849e18d7b70202b922a40ba7330d2521e40d` |
| `app.camera.snapshot` | GATEABLE | `1.1.0` | `SENSITIVE` | `f0f72e98ffbc5be8e331ffdbfcf874619085cd0805bc4ac9ed9a11553dae9063` |
| `app.camera.status` | GATEABLE | `1.1.0` | `INTERNAL` | `6626cb84f0af4925dd3d3501294ae03b8bd2eff81e1fada769262ee9d725742e` |
| `app.camera.stream.start` | GATEABLE | `1.1.0` | `SENSITIVE` | `9ca105b4b3db092dcb32526d3b4be945958d6d81cd22f380999b771345f0a071` |
| `app.camera.stream.stop` | GATEABLE | `1.1.0` | `SENSITIVE` | `586506032246f2e8a35fbaf4e6c7b0bc94f81161ef22a9743c1a87ba7907416a` |
| `app.diagnosis.cancel` | GATEABLE | `1.1.0` | `SENSITIVE` | `ba9de61f695c9c3dcbcfd25ab05d4b81b73f6620c8ed823ee47d6241a7ab855b` |
| `app.diagnosis.evidence` | GATEABLE | `1.1.0` | `SENSITIVE` | `1c4a879bb734a0aede1d9853e0af677247efc3e6cdaf99b5d16823c91c8fa93b` |
| `app.diagnosis.result` | GATEABLE | `1.1.0` | `SENSITIVE` | `d71948803cd929e84ad19deb9313fd4fbce293bfc1a506635fe886259c3cce34` |
| `app.diagnosis.run` | GATEABLE | `1.1.0` | `SENSITIVE` | `49dd99912fbb89f8aaf5a67d8c9484309cce45330fcea883dcd35141aa568ba5` |
| `app.diagnosis.snapshot` | GATEABLE | `1.1.0` | `SENSITIVE` | `60e3c50bab717f03da44e8b2533328d349538ec5200b523499001f06cf56d428` |
| `app.diagnosis.status` | GATEABLE | `1.1.0` | `INTERNAL` | `bb97fb5f1d2605fa74c53aa58f03ac9f1a7a705a81781cdc71ff5c1af5b3564d` |
| `app.event.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `0b1e36cfb84d2768bf2c4daf62571453941e44f41364404ffdf84be9068de98f` |
| `app.event.list` | GATEABLE | `1.1.0` | `SENSITIVE` | `2fe2e585405d47e5b268cb843edd69448489fad699b25846120fcd638fe221cc` |
| `app.gnss.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `944d1e74a96b1fe59fa07964a4eb06877b9860c47c6e9e5491e110d1c7556295` |
| `app.gnss.list` | GATEABLE | `1.1.0` | `INTERNAL` | `804a1f4a8117186940ee085d9fdacc38e9c7943e2975a82788bcb611e96010ba` |
| `app.gnss.sample` | GATEABLE | `1.1.0` | `SENSITIVE` | `ea9eb8b490d9c1f7cf05c3d53790d170241bb7ca34c8f298a7ef257469c1e494` |
| `app.gnss.status` | GATEABLE | `1.1.0` | `INTERNAL` | `cae0e43f5266d6b6cba646b3ec75aa43d9ca7df53f99023269385101875dc523` |
| `app.gripper.status` | GATEABLE | `1.1.0` | `INTERNAL` | `65fc2daa1d22f4b9b2869eef246cc7e7095af4caa018142422a4f060cc6c4ff6` |
| `app.imu.calibration.status` | GATEABLE | `1.1.0` | `INTERNAL` | `1149975c8eb054edcf87650a716f87e638a2c3f5a48b3698325dec16ee5089cc` |
| `app.imu.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `70173f03cfe85bfbe983ef11d21b77eb97253a889e4c696db6b410a411480e8e` |
| `app.imu.list` | GATEABLE | `1.1.0` | `INTERNAL` | `d3fba08dccd9b0012d4abc9fe30463b586789635bd4de43ff96d74bc029157ef` |
| `app.imu.sample` | GATEABLE | `1.1.0` | `SENSITIVE` | `ded0cedcbf245048034dbac73c61951afff048d56936ddcefc498554a8d086be` |
| `app.imu.status` | GATEABLE | `1.1.0` | `INTERNAL` | `3028942371dbd7c2077d18ec26ad0ba0253f6828e1292191a472903670e9fc7b` |
| `app.lidar.calibration.status` | GATEABLE | `1.1.0` | `INTERNAL` | `3a8f1accd584a5b615cb35de97170bb2074931af356891a83917f44d37e9368d` |
| `app.lidar.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `0db2cdac684e3cb9ae1d891ab84b772e92b8f771a70d15532489f68df45a5dd2` |
| `app.lidar.list` | GATEABLE | `1.1.0` | `INTERNAL` | `7bfed839997b2e409e000bdbe08a811dfc5d4a6c69c9cb84858207a9a3ad72ce` |
| `app.lidar.snapshot` | GATEABLE | `1.1.0` | `SENSITIVE` | `6fd90eb65fe95dd7dcdf4d3c82ed3f78cfd4a1c7fe0f7a20a3082c2b32d38d3c` |
| `app.lidar.status` | GATEABLE | `1.1.0` | `INTERNAL` | `be239e77a77879997c5aa4ca62d7fcc1f3ae3569f702693b89eab941ea971ab9` |
| `app.localization.initialize` | GATEABLE | `1.1.0` | `SENSITIVE` | `c3b3f65f9ffb73fd21a4ada944940cf9298cd12ff85bd499706f9292253a84d2` |
| `app.localization.pose` | GATEABLE | `1.1.0` | `SENSITIVE` | `c280e2e721df37831a7a74223f5918b3ed037905d53f0d26cd7ba287fe87d8a4` |
| `app.localization.quality` | GATEABLE | `1.1.0` | `INTERNAL` | `855f0f807893b9645caeab8463b9205980e61bd7033d4351da60c2b45f4d241f` |
| `app.localization.relocalize` | GATEABLE | `1.1.0` | `SENSITIVE` | `f8701f5c1baa8fb6743e4e7aa0ed3c0eb5099fcc7bef362531e862d5fbda2bfd` |
| `app.localization.reset` | GATEABLE | `1.1.0` | `INTERNAL` | `c5929325a6c55a3a0de598a890c2c6dafce5a805ed488d677c8f467a1eceecfe` |
| `app.localization.status` | GATEABLE | `1.1.0` | `INTERNAL` | `1967add5892c7df8f374c608bb965654931c672f97bf903ab1f00e824d388a30` |
| `app.manipulation.plan` | GATEABLE | `1.1.0` | `SENSITIVE` | `d2b6db540f177347bfe184b2aecefba2391feea028f415d960563df354b5d999` |
| `app.manipulation.status` | GATEABLE | `1.1.0` | `INTERNAL` | `9633a8acb55ed1bc1e7b6cafed54aa9074eea8852133c910202a50ed59553f6d` |
| `app.map.clear` | GATEABLE | `1.1.0` | `SENSITIVE` | `db4c63c79285ef89df7a8d1958c50e13ad4baed33f8d3cf7b193fe8842e2f31d` |
| `app.map.create` | GATEABLE | `1.1.0` | `SENSITIVE` | `e724ca8e092b1a85427ad4490499b40ee2146549fdeb90a629bfe54561ce3ec2` |
| `app.map.export` | GATEABLE | `1.1.0` | `SENSITIVE` | `fe8da03642d0ff77fbd2f40ec58e86f2fe753296c0259e3ccd17c605744ff16e` |
| `app.map.import` | GATEABLE | `1.1.0` | `SENSITIVE` | `20a3da9414958ff5083685d654e9ba77f5b1a9748943f9590ddb182f48095a6c` |
| `app.map.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `f11fb1985eb891ca0a87125608b1359d0c962bcfdfe436bbea284dc6e4197251` |
| `app.map.list` | GATEABLE | `1.1.0` | `SENSITIVE` | `a39851f7bfa16d261f295fa5ea0d4bb4f0a2cbeb9c960588441726a014d5e985` |
| `app.map.load` | GATEABLE | `1.1.0` | `SENSITIVE` | `769c8e4321ce7ca82d136e2eb8ead08cec341dd647ef4439305b967a9c32c01b` |
| `app.map.save` | GATEABLE | `1.1.0` | `SENSITIVE` | `7043e54e06b7cfe9a270e012fce3342a4e9d1a9c1df167af656a0f80a42c056f` |
| `app.navigation.costmap.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `feac0abe8822fff0d24a32af842c32d36e40111bd625b6948f4c970c1e6669e9` |
| `app.navigation.path.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `34bfcb3dad7b5f6a306a3b02ec1071d8b146f85a07cbb3fc78298accd42b204f` |
| `app.navigation.plan` | GATEABLE | `1.1.0` | `SENSITIVE` | `ad692d32ec5a57742dfb815c00bf40a16d173ff8ef8cae3dbda94ca25723ea68` |
| `app.navigation.status` | GATEABLE | `1.1.0` | `INTERNAL` | `caf2ace79fae5304feadff92e4df9ebaced386313dc8e1c2095d120ff5ac5e9a` |
| `app.odometry.reset` | GATEABLE | `1.1.0` | `INTERNAL` | `0c16fd8ef8124f5de708250f12439a05fb0e222bd393e91eac259924a244f5b4` |
| `app.odometry.sample` | GATEABLE | `1.1.0` | `SENSITIVE` | `3b9a0eed492163c2dfe05d6695d62f83e9113e694dfda270b25b0d45001a5603` |
| `app.odometry.status` | GATEABLE | `1.1.0` | `INTERNAL` | `e775b371b4ef791d4ae9ba29b5ea246e15568ed283f5a22dfb6a77bd1b3fb8e3` |
| `app.parameter.get` | GATEABLE | `1.1.0` | `SENSITIVE` | `bb26d5211b0cbbf6f442297f9b53b150abf45f5e244899b3aefc876f6656275d` |
| `app.parameter.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `206d96c98dc938cb9754c04af23b16c604a91c684ea028832ea0758228f974a2` |
| `app.parameter.list` | GATEABLE | `1.1.0` | `INTERNAL` | `c9dee69527ddb6c584f2bfc5485f7729bfb3719b04a6e0d0d28a2b1b57b8dfff` |
| `app.parameter.rollback` | GATEABLE | `1.1.0` | `SENSITIVE` | `eaa7bf42d9e5a9d9648dd6cadb4547f87aab4e007e3e68dffbfb15800376bd44` |
| `app.parameter.set` | GATEABLE | `1.1.0` | `SENSITIVE` | `cbd1d219844a7d403d2b629dee2d2d91a9a0c0fea934f3297efa0ac5f078c398` |
| `app.parameter.validate` | GATEABLE | `1.1.0` | `SENSITIVE` | `74b118b9f61384bcc9bce06516919e30686b29be20e1e74df8ce7297c57a55ce` |
| `app.regression.cancel` | GATEABLE | `1.1.0` | `SENSITIVE` | `3e9024319f3646c8c493f855e22ee7b9754f3fba5e00c8af01006fdd8e85be31` |
| `app.regression.plan` | GATEABLE | `1.1.0` | `SENSITIVE` | `8291c9f4d16ed58cb8542ccfb4b28c99c19754398a707fdd290d5ae0156f302f` |
| `app.regression.result` | GATEABLE | `1.1.0` | `SENSITIVE` | `99533235a4055c14fefe92393af447d1a6c3bc3a11cc3548003573bb5e2de192` |
| `app.regression.run` | GATEABLE | `1.1.0` | `SENSITIVE` | `c0e75d912b858d227006414611956941e603b9e15c96b03723ac694840d0a3df` |
| `app.regression.status` | GATEABLE | `1.1.0` | `INTERNAL` | `2534f0a8cce58efadf16a6d205be5cfb1d6cdfef76a01a8c821f3cabe0f9cf62` |
| `app.robot.discover` | RELEASED | `1.1.0` | `INTERNAL` | `7876ac2afb7c6ea6f4d2a6efcf1479601337bc61434176ec7d8a9c34f959e656` |
| `app.robot.health` | GATEABLE | `1.1.0` | `INTERNAL` | `3d3e5d0757295d9b6c9e3f23e387850c55c57a66d5687a0ef543d4fcc322c5e8` |
| `app.robot.status` | GATEABLE | `1.1.0` | `INTERNAL` | `44d5d08599cd23cb75fe8d608466413788d2d67653548b446ae594b5c96fd736` |
| `app.safety.approval.status` | GATEABLE | `1.1.0` | `INTERNAL` | `df6f9d24ed96bc9d9615c9037aa3052272e5ed34163c9002358531ad82b57ee1` |
| `app.safety.emergency_stop` | GATEABLE | `1.1.0` | `INTERNAL` | `5c8e0c5766a3034a9838f6122aba36fc852263bfc890af3857fbc95cac6563e4` |
| `app.safety.interlocks.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `b06d01cb142af1e556ad445862b5d532df1f5337fffc16ed50e9958244688cdc` |
| `app.safety.limits.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `615cc5f655effa1de9682ee514c3a81408f687920c899a1b005a4941117131ea` |
| `app.safety.protective_stop` | GATEABLE | `1.1.0` | `INTERNAL` | `829cad7373b896627c579e6c2f8189e23ca0db37d17c26f0af356bdd0f94582e` |
| `app.safety.status` | GATEABLE | `1.1.0` | `INTERNAL` | `66cba1eadfa64450c14bb2fed846c5b3328d0806acde1822196bec542ef9508e` |
| `app.safety.stop.clear` | GATEABLE | `1.1.0` | `INTERNAL` | `7cf56516c9d5343f70731b6a31a6f4b9c10c6f2692b67d988711b3f3ceee56a1` |
| `app.safety.zones.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `44c4642687d75f9e66ea9baf092f7962bae39bb791996f9b858f1971015d9666` |
| `app.state.snapshot` | GATEABLE | `1.1.0` | `SENSITIVE` | `05cc82ccf040152d0f8856f4cf06acee012f8d26559bc2c27088412b0d2fa4b2` |
| `app.state.watch` | GATEABLE | `1.1.0` | `SENSITIVE` | `bf84ef54eaf86e5276a5ac8b284d3299b36e9885bd94e1083cd53769ab1da5ba` |
| `app.task.cancel` | GATEABLE | `1.1.0` | `SENSITIVE` | `ebe41931d6089b83ea3cdd6f5ea594b3231a994af4157486f0a23f1a0ec5a630` |
| `app.task.describe` | GATEABLE | `1.1.0` | `INTERNAL` | `60b7abf9aa66e37dbe7bd099698b935444440424cc231553694b758f43676660` |
| `app.task.list` | GATEABLE | `1.1.0` | `INTERNAL` | `cfda88e7b83622a2f17ff4302c212e152802a2802fcf4bbb05ef073a3fdea219` |
| `app.task.result` | GATEABLE | `1.1.0` | `SENSITIVE` | `5fbc572358d278410e092fed85014426151cfb21b13c7086f48c35d558dc63fe` |
| `app.task.start` | GATEABLE | `1.1.0` | `SENSITIVE` | `fbb41bdd3268f404eb6ef4c56fc26ea9c1b32c48115dadf9c16188ca75323aac` |
| `app.task.status` | GATEABLE | `1.1.0` | `INTERNAL` | `f5a060a38d5f351ab649f60c2c15990bcee1c93e33ad7c3de585f768902e76f7` |
| `app.telemetry.export` | GATEABLE | `1.1.0` | `SENSITIVE` | `6de2bcc7352be7d7283d29c28241a170294661a91da058fe898127ee75efabe5` |
| `app.telemetry.snapshot` | GATEABLE | `1.1.0` | `SENSITIVE` | `7febbe20318b3e1b588015b34ef89167b3ebdaa7bd9bee2958adab33f701fb59` |
| `app.telemetry.watch` | GATEABLE | `1.1.0` | `SENSITIVE` | `a919ded06f4bb596ded1833068f9c9b7d31716209380bc8bdcfe2e86ea19a227` |
| `app.teleop.velocity` | GATEABLE | `1.1.0` | `INTERNAL` | `2e779398303a5f810f7c328a6f20af4d82ccbb4513eaa626257be3e8e33e9661` |
| `app.test.cancel` | GATEABLE | `1.1.0` | `SENSITIVE` | `60edabf0d07b75a056cb4e63c035ae469311f69e5d343dd03d5b3b5a0379238d` |
| `app.test.describe` | GATEABLE | `1.1.0` | `INTERNAL` | `43d8478f1e363b94336f80ca78110f007c3297286b418cddbc57ebe8155e9330` |
| `app.test.evidence` | GATEABLE | `1.1.0` | `SENSITIVE` | `f67ae71dade76213a6436f898c929082083498a1bb29d66d605cf3deae058da0` |
| `app.test.list` | GATEABLE | `1.1.0` | `INTERNAL` | `759bf06cac632c9afb3e122a73601b4df356366035de4f0f438cc7e4b9c6bf2e` |
| `app.test.plan` | GATEABLE | `1.1.0` | `SENSITIVE` | `19924a75ac4f2db893af602dd4f000317db06f87773ed0eb90c618352a0b11d1` |
| `app.test.result` | GATEABLE | `1.1.0` | `SENSITIVE` | `e7b2c4a2eaa583dbda543535d16f1c553ea177320b08e944264fa58668a6adee` |
| `app.test.run` | GATEABLE | `1.1.0` | `SENSITIVE` | `9bf2c3ad298ec6fbee63a5b71538cb5de79cdb5ad9b189156e4cd29166d85b22` |
| `app.test.status` | GATEABLE | `1.1.0` | `INTERNAL` | `fc7aabd22e243732bc722ca29a030055c66ccecd17d8fb718b45e90e0d323904` |
| `app.tuning.baseline.create` | GATEABLE | `1.1.0` | `SENSITIVE` | `5d37ec07039e11fab1a2854b8fb06d9eae869947224257b7acbad28aaf09e05c` |
| `app.tuning.candidate.create` | GATEABLE | `1.1.0` | `SENSITIVE` | `2774804daae567cd64531b2709ff2a5f4de4599faffe879eda3c38f8af5e67a2` |
| `app.tuning.candidate.evaluate` | GATEABLE | `1.1.0` | `SENSITIVE` | `8f6b8826c78891fa3a1d4b314681d271764473dbf3af9016fa9097251033f4e1` |
| `app.tuning.commit` | GATEABLE | `1.1.0` | `SENSITIVE` | `766dc576f57088f6d011ffd04fb024c37de2da4e892230c1bddc6c35536ded16` |
| `app.tuning.rollback` | GATEABLE | `1.1.0` | `SENSITIVE` | `edd3b13b89d58c520ab2df6bf339c33b3b3c17122d09ba8523f71db27b27f75c` |
| `app.tuning.status` | GATEABLE | `1.1.0` | `INTERNAL` | `776530585236c9b5809731f7b58051f28f87249d36c5f04c88735133326b8099` |
| `checkpoint.create` | GATEABLE | `1.1.0` | `SENSITIVE` | `a4062da2481aecdde201e199976d89a98261cf5d4f0c37207c6bf121cf840cd9` |
| `checkpoint.list` | GATEABLE | `1.1.0` | `SENSITIVE` | `b8c9383d0eb6683c68c250ea6b4f0a004b1a0b3530a901d7370d1369babeea85` |
| `checkpoint.restore` | GATEABLE | `1.1.0` | `SENSITIVE` | `1b602711e252fc95d245fce524f3df3dc96043d82b38d655c919a71382fa9cce` |
| `episode.export` | GATEABLE | `1.1.0` | `SENSITIVE` | `56d90270e369b875d0a850d57fa5b9eafdeca896b3445260c8f6f540d9603d1f` |
| `episode.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `2fec7f854e4472fc2880929adc7070904b7dc368045773281da6d789468e5f7c` |
| `episode.list` | GATEABLE | `1.1.0` | `SENSITIVE` | `fb91ed11d0fd50b28ab74cb1a327e8672aab59dbffe4f59f61b8f68b6dc1dab5` |
| `evidence.resolve` | RELEASED | `1.1.0` | `INTERNAL` | `c970444abe7953f2959d405a54a11b9f21d1b10b343d5342e6074fec25eb3ba8` |
| `hw.actuator.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `97878a537f1d4f1b2f053cc969a220e1373d719ddb2069001dbb14de036fc57c` |
| `hw.actuator.list` | GATEABLE | `1.1.0` | `INTERNAL` | `7a97cb14384390bfebaeeb7b159872e4ac66b955c1152191ef4ab5d5bd568458` |
| `hw.actuator.status` | GATEABLE | `1.1.0` | `INTERNAL` | `7e811b3c1f6dd05131e9a5c461deb2c865505d861aa2485ac7921e0b05ad445e` |
| `hw.bus.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `8e5f0f4aa8a30feb749e33eac8d8dd3195475d2c59a43e9daf190ff6f4dbf37b` |
| `hw.bus.list` | GATEABLE | `1.1.0` | `INTERNAL` | `2575780c3ce4aff6fe4c3a192e47d640f16e173c69499bf1519d58322ce4d1d7` |
| `hw.bus.scan` | GATEABLE | `1.1.0` | `INTERNAL` | `81779c981c8490a30d7fd3592434bceef086452b7d4bc76e3bb29d1b47ac760b` |
| `hw.bus.statistics` | GATEABLE | `1.1.0` | `INTERNAL` | `b81d4247f085424b27aacd553887af8ce89ae32431962f52fc15e531b0cd4dbe` |
| `hw.bus.status` | GATEABLE | `1.1.0` | `INTERNAL` | `c5e5de974fee7b99369285f6f279ce770d778c68b2cb32a56dcfe797f6045f53` |
| `hw.clock.status` | GATEABLE | `1.1.0` | `INTERNAL` | `d09dc5fd8218e22a988e370a6cd65b3ec4cbde39759af410efd2b3e2f942dc10` |
| `hw.compute.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `b84df63eb5d9067ccd081fb4f9bea33f930f546ee4f0d7c158ae717fe12be6bd` |
| `hw.compute.list` | GATEABLE | `1.1.0` | `INTERNAL` | `2f73d01bca002a5f45959b8850fc736f192e27404cd3c8cdfa3e5ce011e4f3d5` |
| `hw.compute.status` | GATEABLE | `1.1.0` | `INTERNAL` | `746c3443a62030f2b91ad04bf2a1778ef85b06e3d9e22c8d9b67416dda42af58` |
| `hw.firmware.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `a7088d2f0b1141071d7fb3a8ff45933006e03479a4203c6eb93aed626167c932` |
| `hw.firmware.list` | GATEABLE | `1.1.0` | `INTERNAL` | `d973d3eef610a61a67a277f3ea200e71ec59a6b73399e6bc59c8d3cf032fd9fe` |
| `hw.firmware.verify` | GATEABLE | `1.1.0` | `INTERNAL` | `7d6d4fde0756a2edc6d9e0d5dadf3b3abce7238b3dd116d5bbd1f2dd13f68441` |
| `hw.inventory.scan` | RELEASED | `1.1.0` | `INTERNAL` | `5a0bd33a98e9c5b667c3e29fd0f7e2dedb0969d68242b6714ec82871b6aa56e1` |
| `hw.power.battery.status` | GATEABLE | `1.1.0` | `INTERNAL` | `00b3dbaeaf4df3f9c8717b1f49fb11d168580ef61c7f12750291e815528bd903` |
| `hw.power.rail.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `d09173b9a862dda4aae026f834ac9ca4559aa23377189d537176a0e48955571e` |
| `hw.power.rail.list` | GATEABLE | `1.1.0` | `INTERNAL` | `e77a2818851457241d183a41f9975dbef605f6f3be8d98691cf92ae262f62dbd` |
| `hw.power.status` | GATEABLE | `1.1.0` | `INTERNAL` | `4da57902922ed19a5498ba1d8f95349bfeafeac7ef5fb26a089ea2a0c9f66541` |
| `hw.sensor.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `148b89a33c8baad88276ccb6992bbf4b7dfeef881507fe0a43bc8191201c7102` |
| `hw.sensor.list` | GATEABLE | `1.1.0` | `INTERNAL` | `e23aa5cf3021020fc5f449b728dedb045e49382e2073d4b84ce2e7a4dce86995` |
| `hw.sensor.read` | GATEABLE | `1.1.0` | `SENSITIVE` | `f161dd4068b10798c7666697a326514379e84b3ca42cd18be42b55114e6a948a` |
| `hw.sensor.status` | GATEABLE | `1.1.0` | `INTERNAL` | `eab48b87c4937fa5fa1be9c4a3e57702818e1eed40bc53f768d9d3d689cabb83` |
| `hw.storage.status` | GATEABLE | `1.1.0` | `INTERNAL` | `ebed9d7a0918f007a6e96b406f8ee1759a48d3462c507e30340bd3a7a1bf167c` |
| `hw.thermal.status` | GATEABLE | `1.1.0` | `INTERNAL` | `a7aec29bece1ec720186ee30139ecb5c7445076f02f0472e2504f1c001fb14e2` |
| `linux.binary.describe` | RELEASED | `1.1.0` | `INTERNAL` | `9ea47ebf61e901c0a8aca952db951b03e50f5fd0c23d9840513cd437c4d6fda9` |
| `linux.binary.verify` | RELEASED | `1.1.0` | `INTERNAL` | `7c14730c9ae5fe5290c55d478563dc1dfb2beb64e7036090121f06afd58b8820` |
| `linux.cli.probe` | RELEASED | `1.1.0` | `INTERNAL` | `8b3f7bafbd291c96bef43deba247cb7e3a1481048c2a8b5fa25beda1a5317315` |
| `linux.config.apply` | GATEABLE | `1.1.0` | `SENSITIVE` | `1a62958e8cb819aa320ada769fa2e573e7b9e6aafbf2aa9e1244e97d2076c58f` |
| `linux.config.diff` | GATEABLE | `1.1.0` | `SENSITIVE` | `f48f6a86d720493153597d7479d61d0d142f8b56d59735e363a32f6de6ac3664` |
| `linux.config.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `6d7d87d69607eee25fdb8f2f3439a859362f4b2985c82185d1e2ab8438fec466` |
| `linux.config.locate` | RELEASED | `1.1.0` | `INTERNAL` | `df7c834f237b51af47d08755301d4054cc797a6286778b76d9a194319b79f1e6` |
| `linux.config.rollback` | GATEABLE | `1.1.0` | `SENSITIVE` | `0c94e247e881f7e1772de8dd204563c60569733812d8c165dae8ae0612ce767f` |
| `linux.config.validate` | GATEABLE | `1.1.0` | `SENSITIVE` | `a89c05f09089c08b7c288c7eb6b0c4dc37923257758c9fb52aaa5b45f70b1a18` |
| `linux.container.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `73a5feabf1d7ad5783973def82e7dabf291e0c51260addfe8e9afe10a2282aaf` |
| `linux.container.list` | RELEASED | `1.1.0` | `INTERNAL` | `cfa2713eece87fa2ffaf844de4af3616fe4324a98141095a8cef7764d152ade7` |
| `linux.container.logs` | GATEABLE | `1.1.0` | `SENSITIVE` | `41d9ff7e48ab130a0edde8eca1af8b9f5f3656a69dfcab1a479fd46d8b69fc86` |
| `linux.container.restart` | GATEABLE | `1.1.0` | `INTERNAL` | `aabf4a1fcbed0a5c944049138fcf736b83aef844fe5101986038f32e0db6f697` |
| `linux.container.start` | GATEABLE | `1.1.0` | `INTERNAL` | `4eea5871ca225e8e68126f49d0418fa8947a77967e3344752ceac230ca170c9a` |
| `linux.container.stats` | RELEASED | `1.1.0` | `INTERNAL` | `0eb276c74bb0db6e7d19f0c219d485907208905fc8e4849210287e8eaf3d3e7f` |
| `linux.container.stop` | GATEABLE | `1.1.0` | `INTERNAL` | `e18f858f180252e914d3ef7e6693834bf10c93c8678d343f75cf5af17e6cae16` |
| `linux.file.hash` | RELEASED | `1.1.0` | `INTERNAL` | `0090032988e2d8f1ef0578dc3878cd8737740b499463e49f200a3e1127690173` |
| `linux.file.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `7982185a65b041bb13b8c0104c301511b7a65cb3052eeeb58c314294a02e8998` |
| `linux.file.list` | RELEASED | `1.1.0` | `INTERNAL` | `5badb21f4c68960a74157e9f102ebcb1ff95b65fcac23b7ecfe4215669d5e74f` |
| `linux.file.read` | GATEABLE | `1.1.0` | `SENSITIVE` | `267c8d9148b2894cb3675eddc10efe1040ec540bd4c6d9afd8880c4c421b851c` |
| `linux.host.inventory` | RELEASED | `1.1.0` | `INTERNAL` | `ac3c070fef7b97ee3d2e6662802b7b1777b01428999f1f67901fe47ec8349d49` |
| `linux.host.reboot` | GATEABLE | `1.1.0` | `INTERNAL` | `a71aa84ab91fa034e007903ab080cd253a03ca81dba3e9f1b5ef83a2565c334d` |
| `linux.host.shutdown` | GATEABLE | `1.1.0` | `INTERNAL` | `0b4a32e6c6a77fa9427045edf58d8fcd4a01a86b71af437f3c593d3efaf802dd` |
| `linux.host.status` | RELEASED | `1.1.0` | `INTERNAL` | `902b98067b616710e7201bff6ede51b15c98e23f1420ebfce45fa0e0800eca29` |
| `linux.host.uptime` | RELEASED | `1.1.0` | `INTERNAL` | `a060740ffc3cc4fb4898ed1ac635109b12089918ad3dcc7a5a26bc9d680fb6bd` |
| `linux.log.follow` | GATEABLE | `1.1.0` | `SENSITIVE` | `9e57e5f6a8d59de9e24b4dd5f38264a17330e2cdc9fc740cd59e6202a19cc12f` |
| `linux.log.query` | GATEABLE | `1.1.0` | `SENSITIVE` | `be462903e9127feb0aa06c9494fe197dcde6f3d7987c12430c319c1f60400b74` |
| `linux.network.connections` | RELEASED | `1.1.0` | `INTERNAL` | `e0496517def5c14411846b3639d849140930be869c57e461e833bab75a9673e0` |
| `linux.network.dns` | RELEASED | `1.1.0` | `INTERNAL` | `77ef7d805c5e508ff4567cab6d701dec2d57e0ef728d154005b94f0f9a6c3c4d` |
| `linux.network.interfaces` | RELEASED | `1.1.0` | `INTERNAL` | `2224a040971b208b60cb24c907b213b367d67bad42bd57637f8a83692b41f242` |
| `linux.network.listeners` | RELEASED | `1.1.0` | `INTERNAL` | `19438cc677e473cbd6e4a692ab2ead5714f68d9e284ae720dab99a27589f7713` |
| `linux.network.routes` | RELEASED | `1.1.0` | `INTERNAL` | `f41505e7aafff692fef54eb184f9c14822c1383d4547e80e5115252b17895148` |
| `linux.network.statistics` | RELEASED | `1.1.0` | `INTERNAL` | `bf6a48e11088b6deada9fb74dc7d239b26880183bbfbff25f697a0c5a95b7fb6` |
| `linux.package.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `7f030f057abfc1b5660cb37fc074009d4b3e0af2ee7c2476bc8c1754241fa153` |
| `linux.package.verify` | RELEASED | `1.1.0` | `INTERNAL` | `9a0057221b2cf37455327ac153b33c6ebd215d53efa58d3682e087fc20688b48` |
| `linux.process.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `62b65eefe6fda8334afa000a9c43752aa7718122b12f85c1ef31f40fb825513c` |
| `linux.process.list` | RELEASED | `1.1.0` | `INTERNAL` | `f170a7e39e28ee35d824b9b0d19bb85ffb2dc140012599f3db3d9152d8f43db6` |
| `linux.process.logs` | GATEABLE | `1.1.0` | `SENSITIVE` | `9d6ecc1da31f274d618b580cf756923685f41b6928df5379e15cfceaf98fec1a` |
| `linux.process.resources` | RELEASED | `1.1.0` | `INTERNAL` | `799d091ca798b989ccc24794169fefd3b661d726e3d8368e18897c9e940a16ac` |
| `linux.process.restart` | GATEABLE | `1.1.0` | `INTERNAL` | `4e5b742d88c27a1a5344b082769c4fd249703f5b448eab199f293940d5d91561` |
| `linux.process.signal` | GATEABLE | `1.1.0` | `INTERNAL` | `942672419771cd720c99ee51f0718d3f7d45a520dd43f08dc02f904651eb4abb` |
| `linux.process.start` | GATEABLE | `1.1.0` | `INTERNAL` | `854ac78276ac64c5c8ba9be45725161b8bff9460302901f14813f04959f3d1d1` |
| `linux.process.stop` | GATEABLE | `1.1.0` | `INTERNAL` | `64e2b24d823572c17de43d5af32e8e65b847862af476222bcde465d0fbce7c38` |
| `linux.resource.cpu` | RELEASED | `1.1.0` | `INTERNAL` | `be8786ee0fd41a7aa37383027fa071fdd83287815a60790a9428d72351193f26` |
| `linux.resource.disk` | RELEASED | `1.1.0` | `INTERNAL` | `fe28f84d92f69da92d7992a4234543c6d45a9452e900373378789fba68d9f502` |
| `linux.resource.gpu` | RELEASED | `1.1.0` | `INTERNAL` | `1bc66d597892890e4cf517dba0d3def5ced3afdd076bc17b591291acb475453f` |
| `linux.resource.memory` | RELEASED | `1.1.0` | `INTERNAL` | `2f0f241a30af3091419dee43a1f59fba22fe78fedd6c93742f98f8743a8df1f3` |
| `linux.resource.snapshot` | RELEASED | `1.1.0` | `INTERNAL` | `2fd77a98621c8940330fb4d282db16fe905055248a471509315ad7fccbc75423` |
| `linux.schedule.disable` | GATEABLE | `1.1.0` | `INTERNAL` | `d6c6073956b5717305b56ae58362998fb2bc60f1a1f2adab4a248d529788c750` |
| `linux.schedule.enable` | GATEABLE | `1.1.0` | `INTERNAL` | `71dbf0d047cee0387d80084fdfd11b8167f91fa9942712adb3c60318035ef8cd` |
| `linux.schedule.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `0628481b0dadde2afba4b40b18363e84b5a98428a36cbcf4ee04755f600d800f` |
| `linux.schedule.list` | RELEASED | `1.1.0` | `INTERNAL` | `f246a5e208f6c932f35a70f8861266494a22d9c74d23251987ed35ea14ae87b9` |
| `linux.schedule.run` | GATEABLE | `1.1.0` | `INTERNAL` | `5c9db1b7b741e726624b0194dc0e7bbb7ce4182f6b5780e5425c3735de4f33a0` |
| `linux.service.disable` | GATEABLE | `1.1.0` | `INTERNAL` | `d901534ec3afa5469eff0df0c58d6c18da334954561886b04dd6d3601051d921` |
| `linux.service.enable` | GATEABLE | `1.1.0` | `INTERNAL` | `744f891ac1a998ed3df9093dd016ef7bee162311393a377919ff0e649d61adcb` |
| `linux.service.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `8f7e220306b3887aaf815570ba3581c6f2a924ceb899fd5753b303132364509f` |
| `linux.service.list` | RELEASED | `1.1.0` | `INTERNAL` | `779b06af95ae477dcab3c05801ebb8cf9ee2a821065a40ae72899988b05b676b` |
| `linux.service.logs` | GATEABLE | `1.1.0` | `SENSITIVE` | `38ec1acfab743a12df0400bb277b01d8d4f7b3625aa78794ce0e2655028f5150` |
| `linux.service.restart` | GATEABLE | `1.1.0` | `INTERNAL` | `fb268ba8da22f13b2df0bbae348b396ccee16c0af6a8f1e3de486287c2b0cb77` |
| `linux.service.start` | GATEABLE | `1.1.0` | `INTERNAL` | `caa7061ada0df217ece1090d33c8116d83ed725193e709a01c4ceb46017fa7b5` |
| `linux.service.stop` | GATEABLE | `1.1.0` | `INTERNAL` | `ba85102f1184891115a42442193f067ee2ff2d6278b26ea22e4849bdc217f175` |
| `linux.time.status` | RELEASED | `1.1.0` | `INTERNAL` | `9688e8586a617e3cc4630ac87d7bb20e5806033ecac0a4ff409782de5dd34b09` |
| `linux.time.synchronize` | GATEABLE | `1.1.0` | `INTERNAL` | `4144fe96e14109e3ef710e6bd8992eb2ea10fddcc31b82ffec3a418efe1e2227` |
| `middleware.graph.snapshot` | RELEASED | `1.1.0` | `INTERNAL` | `4ccaf404c971b8fb9066cbf1cfe65e6c4f39277574041f9095d7b44ecb4575cb` |
| `middleware.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `4acd116d92242c36badfcb47351a8b729b335c1c11ce3ece66934ee4c7a27439` |
| `middleware.status` | RELEASED | `1.1.0` | `INTERNAL` | `e6d96ec293e77cefa6592b00bea8469d608a9bfd9b808e5daef31182bed8adb4` |
| `ros.action.describe` | RELEASED | `1.1.0` | `INTERNAL` | `a103b3947e75f4bf79a20e453b6532213c9648c763c54d3004d1038afebffaf9` |
| `ros.action.list` | RELEASED | `1.1.0` | `INTERNAL` | `0a5b0760cafd3595359729bf98c3f7d73902a18a3901ca3ef38a501b81d6b68c` |
| `ros.action.status` | GATEABLE | `1.1.0` | `SENSITIVE` | `0af4e2835e25dacb70743976c0ad6f8fdf10853ec84d7ffb69d5416d4fa286ac` |
| `ros.bag.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `d312aaf354cfe8d76a6311533f6797852c6b2fdbb04bdaa7ef8e8925b59319d4` |
| `ros.clock.status` | RELEASED | `1.1.0` | `INTERNAL` | `0a7ef2afb29732ba95356c46b2518c3186eaea3c9832b53393cc7f9cbdc7372f` |
| `ros.diagnostics.snapshot` | GATEABLE | `2.0.0` | `SENSITIVE` | `144d9c5724a67f1b00c858eeaebf2a625788b94b2a0cb84ea8430c7173c5a65f` |
| `ros.diagnostics.watch` | GATEABLE | `1.1.0` | `SENSITIVE` | `639a1b2ed3bdb30eaac19b097d99ee249b5177618051e80dc848a7dc218c1ecd` |
| `ros.graph.snapshot` | RELEASED | `1.1.0` | `INTERNAL` | `ac73b823658cdad95610a27614ca9069c8f30256586960b57e3c8a7afe47610e` |
| `ros.node.activate` | GATEABLE | `1.1.0` | `INTERNAL` | `016fa9dadf8aaab6ed8e3b8b406ff8fbe68d1d8dea1e6041427fca9feb684d6d` |
| `ros.node.deactivate` | GATEABLE | `1.1.0` | `INTERNAL` | `9854d3d8eabe0c5ce5458cb74a3449cc52fb54b73ba346362cae6e2bec30e491` |
| `ros.node.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `7a3d5df53b9c79d92b92bf53c86dd7859e609d2e983f74c01f515e72acba5eb5` |
| `ros.node.lifecycle` | RELEASED | `1.1.0` | `INTERNAL` | `251123aa597d0156cee27e1e67b8ea086c618857d390b693cd7c694ade7cebe6` |
| `ros.node.list` | RELEASED | `1.1.0` | `INTERNAL` | `0ba9f5545d67b912a3f9e7964d777dd8b18f1be807f69eda51f62588804dcae2` |
| `ros.node.status` | RELEASED | `2.0.0` | `INTERNAL` | `a0e964e1fa955d618bd858c894482f930f82f2a6f2c1462210582e67f012a58e` |
| `ros.parameter.describe` | RELEASED | `1.1.0` | `INTERNAL` | `66c4295a9c279bd0676a97abef2ffb6af39f750e899dbe077db1e15419f357d8` |
| `ros.parameter.dump` | GATEABLE | `1.1.0` | `SENSITIVE` | `9d867719dc2e7490f43f59c6bb6110234ae96293aabb3fc7501100f4802c04a4` |
| `ros.parameter.get` | RELEASED | `1.1.0` | `SENSITIVE` | `aa03ac032dbb357d4630aaa6a532ff27f18a1e701445bef704c35ba7a7df9ab8` |
| `ros.parameter.list` | RELEASED | `1.1.0` | `INTERNAL` | `77ccc4c8687e0306341d3f424c1df0f2516dbdce4a37e9d76d40d5c0a0cff12a` |
| `ros.parameter.load` | GATEABLE | `1.1.0` | `SENSITIVE` | `9c92d4dfd4cdaf95445dbfab0b6be171ea9974490f9ee5bca8a58e5842f25d28` |
| `ros.parameter.rollback` | GATEABLE | `1.1.0` | `SENSITIVE` | `43bb9088f8c41b2348869a7d66f0ec0bfd49923191d057963fc2294da01ffadd` |
| `ros.parameter.set` | GATEABLE | `1.1.0` | `SENSITIVE` | `8a057246237d6aa173daa8708d209cdf5e1fa2fa5d22337839fdd70fa52ba300` |
| `ros.service.describe` | RELEASED | `1.1.0` | `INTERNAL` | `ac0b23b6788a0069fc79f0e2418ed3b71bf21323dff5febfe3a8e5afcfcb89ca` |
| `ros.service.list` | RELEASED | `1.1.0` | `INTERNAL` | `ec1f2adc21765f60e9c79d50d3bad9f5cd54eabc079c5dc8a4cefe191a582f70` |
| `ros.tf.lookup` | GATEABLE | `1.1.0` | `SENSITIVE` | `2f70467c7ba9e850f14712066660babcc5866dd2a5d98d2463f4f3328078973a` |
| `ros.tf.monitor` | GATEABLE | `1.1.0` | `SENSITIVE` | `a49d454fe19ee07e95f543cfda003b824c02645f22a8087a40a9cc957a337985` |
| `ros.tf.snapshot` | GATEABLE | `1.1.0` | `SENSITIVE` | `6654249a659053acc718065d0ca578e063e39c23713e8507e43075067a27faac` |
| `ros.tf.tree` | GATEABLE | `1.1.0` | `SENSITIVE` | `833dcd738f54c10c2aa153c61f7f69c8b5bd4dbeef5b8f623f5ac439be8526fc` |
| `ros.topic.bandwidth` | GATEABLE | `1.1.0` | `INTERNAL` | `7347e00c188e8b3a4c6941494eee6dd61339071c73171cc1d44e6c31dc852338` |
| `ros.topic.describe` | RELEASED | `1.1.0` | `INTERNAL` | `b7a1f69371c5ab9884f9b47928277b49c7bce6cc28f528bd9159ea48d33a9f32` |
| `ros.topic.list` | RELEASED | `1.1.0` | `INTERNAL` | `bdc3122355a2afd0494871dd39461c95087237e3f56428736be6548e35c05e24` |
| `ros.topic.rate` | GATEABLE | `1.1.0` | `INTERNAL` | `2b1b373afaea5a9ccdf69a7b58a6acb403be5a04b296d0825ab50f87ae158f10` |
| `ros.topic.sample` | GATEABLE | `1.1.0` | `SENSITIVE` | `efba3bfee2a8cd6683e2602e2f43aa80c24886a404bd8568cdca140222e506ce` |
| `runtime.health` | RELEASED | `1.1.0` | `INTERNAL` | `a0c6413ec9c6e1c817897265ab65cf7b0eefbe3ee36e33802615e4aac328387f` |
| `runtime.version` | RELEASED | `1.1.0` | `PUBLIC` | `4debde3f3043ae71d2609d2b1b31bf5bd71e62f367a43c1afb1b3e1b15dce624` |
| `state.graph.query` | RELEASED | `1.1.0` | `INTERNAL` | `ed5da2053b763126ef4366e91c57749ade2b05af71ed9a2ca14a54f0ea30dae1` |
| `state.graph.snapshot` | RELEASED | `1.1.0` | `INTERNAL` | `b797a0713ce068e6e9cd8a51615c85b4a50cc8a050b50f6c1d56371f699e2a44` |
| `tool.catalog` | RELEASED | `1.1.0` | `INTERNAL` | `c1a599f007eec664ef961a173aa6e9b5d88770b93b3f5c2029418cdef2c7a3f0` |
| `tool.schema` | RELEASED | `1.1.0` | `INTERNAL` | `737435d57292f7665dcf78a7693c435af9c5d5fd90e91018b5d025a8fa478beb` |

## `app.base.status`

Read mobile-base readiness, control mode, and bounded health metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `a86e2e8bd0f0cf83df6f4203b5615bcc6a7b51efbc66c443d3c4c664d3cf0e47`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.calibration.inspect`

Inspect scope, prerequisites, and bounded metadata for one calibration.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `79442bd94b62c07fc17589eab66fbc33e3fead8a82f4d8fb04ff004351636233`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "status": {
          "type": "string"
        },
        "health": {
          "type": "string"
        },
        "frame_id": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.calibration.list`

List target-defined calibration procedures and their stable identifiers.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `25f5c2e0418fd9834a74100c923f7ebdb39c1b781ab2da9be92162a47fdac9b2`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "status": {
            "type": "string"
          },
          "health": {
            "type": "string"
          },
          "frame_id": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.calibration.status`

Read lifecycle state and last known outcome for one calibration.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `9575987f77a34dbb909bb3cf2d08178acedc9c2a87d8bb182a91fecc31bad7e5`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.calibration.validate`

Validate one calibration candidate without applying it to target hardware.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `a59aab3bff256f641032ea101eacf189bd22282429c10191c7518c2a122471fc`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "candidate_ref": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id",
    "candidate_ref"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "valid": {
      "type": "boolean"
    },
    "findings": {
      "type": "array",
      "maxItems": 100,
      "items": {
        "type": "string"
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "valid",
    "findings",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.camera.calibration.status`

Read calibration availability, identity, and age for one camera.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `0c02ac3a7894e04315d62b3b3df64a8527e8d60e4d159a1e4567a0631c02d6ad`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.camera.inspect`

Inspect identity, frame, format, and bounded metadata for one camera.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `1c089c659d2b9ee0a43f36dd20cf652b29c5b2dff2b5ed56092db38a5ea9747e`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "status": {
          "type": "string"
        },
        "health": {
          "type": "string"
        },
        "frame_id": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.camera.list`

List application-visible cameras with stable identity and frame metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `fe823d481b447927b4c38a998efe849e18d7b70202b922a40ba7330d2521e40d`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "status": {
            "type": "string"
          },
          "health": {
            "type": "string"
          },
          "frame_id": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.camera.snapshot`

Capture or reference one bounded frame from a selected camera stream.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `f0f72e98ffbc5be8e331ffdbfcf874619085cd0805bc4ac9ed9a11553dae9063`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "camera": {
      "type": "string"
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "camera": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "timestamp": {
      "type": "string"
    },
    "frame_id": {
      "type": "string"
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.camera.status`

Read stream availability and health for one application-visible camera.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `6626cb84f0af4925dd3d3501294ae03b8bd2eff81e1fada769262ee9d725742e`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.camera.stream.start`

Start a bounded camera stream session with explicit lifetime and byte limits.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `SESSION_HANDLE`
- Observation overhead: `BOUNDED`
- Execution mode: `SESSION_START`
- Paired operation: `app.camera.stream.stop`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `9ca105b4b3db092dcb32526d3b4be945958d6d81cd22f380999b771345f0a071`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "camera": {
      "type": "string",
      "minLength": 1
    },
    "ttl_s": {
      "type": "number",
      "minimum": 1,
      "maximum": 300
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 100000000
    }
  },
  "required": [
    "camera",
    "ttl_s",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "session_id": {
      "type": "string"
    },
    "expires_at": {
      "type": "string"
    },
    "stream_ref": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "session_id",
    "expires_at"
  ],
  "additionalProperties": false
}
```

## `app.camera.stream.stop`

Stop one camera stream session identified by its opaque session handle.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `SESSION_STOP`
- Paired operation: `app.camera.stream.start`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `586506032246f2e8a35fbaf4e6c7b0bc94f81161ef22a9743c1a87ba7907416a`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "session_id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "session_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "session_id": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "session_id"
  ],
  "additionalProperties": false
}
```

## `app.diagnosis.cancel`

Request ordinary cancellation of one target-bound diagnosis run.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `ba9de61f695c9c3dcbcfd25ab05d4b81b73f6620c8ed823ee47d6241a7ab855b`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "run_id": {
      "type": "string",
      "minLength": 1
    },
    "reason": {
      "type": "string",
      "maxLength": 512
    }
  },
  "required": [
    "run_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "run_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "run_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.diagnosis.evidence`

List bounded artifact references associated with one diagnosis run.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `1c4a879bb734a0aede1d9853e0af677247efc3e6cdaf99b5d16823c91c8fa93b`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "artifacts": {
      "type": "array",
      "maxItems": 256,
      "items": {
        "type": "object",
        "properties": {
          "artifact_ref": {
            "type": "string",
            "minLength": 1
          },
          "media_type": {
            "type": "string"
          },
          "observed_at": {
            "type": "string"
          }
        },
        "required": [
          "artifact_ref"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "artifacts",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.diagnosis.result`

Read the bounded conclusion document for one completed diagnosis run.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `d71948803cd929e84ad19deb9313fd4fbce293bfc1a506635fe886259c3cce34`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "result": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "result",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.diagnosis.run`

Submit one bounded diagnostic run under external R3 authorization.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R3`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_PLAN, INTERLOCK_BLOCKED, BUSY, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `49dd99912fbb89f8aaf5a67d8c9484309cce45330fcea883dcd35141aa568ba5`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "diagnosis_profile_id": {
      "type": "string",
      "minLength": 1
    },
    "evidence_set_id": {
      "type": "string",
      "minLength": 1
    },
    "mode": {
      "type": "string",
      "enum": [
        "passive",
        "active"
      ]
    },
    "max_run_duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 86400
    }
  },
  "required": [
    "diagnosis_profile_id",
    "evidence_set_id",
    "mode",
    "max_run_duration_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "run_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "run_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.diagnosis.snapshot`

Read a bounded diagnostic evidence snapshot without asserting a diagnosis conclusion.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `60e3c50bab717f03da44e8b2533328d349538ec5200b523499001f06cf56d428`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string"
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 10000000
    }
  },
  "required": [
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "snapshot": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "snapshot",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.diagnosis.status`

Read lifecycle state and bounded progress metadata for one diagnosis run.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `bb97fb5f1d2605fa74c53aa58f03ac9f1a7a705a81781cdc71ff5c1af5b3564d`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.event.inspect`

Read the bounded structured details for one application event identity.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `0b1e36cfb84d2768bf2c4daf62571453941e44f41364404ffdf84be9068de98f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "event": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "type": {
          "type": "string"
        },
        "occurred_at": {
          "type": "string"
        },
        "source": {
          "type": "string"
        },
        "severity": {
          "type": "string"
        },
        "details": {
          "type": "object",
          "properties": {},
          "additionalProperties": true
        }
      },
      "required": [
        "id",
        "type",
        "occurred_at",
        "details"
      ],
      "additionalProperties": false
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "event",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.event.list`

List bounded application event metadata with optional time and cursor filters.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `2fe2e585405d47e5b268cb843edd69448489fad699b25846120fcd638fe221cc`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "since": {
      "type": "string"
    },
    "until": {
      "type": "string"
    },
    "cursor": {
      "type": "string"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    }
  },
  "required": [
    "limit"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "maxItems": 1000,
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "type": {
            "type": "string"
          },
          "occurred_at": {
            "type": "string"
          },
          "source": {
            "type": "string"
          },
          "severity": {
            "type": "string"
          }
        },
        "required": [
          "id",
          "type",
          "occurred_at"
        ],
        "additionalProperties": false
      }
    },
    "next_cursor": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.gnss.inspect`

Inspect identity, supported constellations, and metadata for one GNSS receiver.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `944d1e74a96b1fe59fa07964a4eb06877b9860c47c6e9e5491e110d1c7556295`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "status": {
          "type": "string"
        },
        "health": {
          "type": "string"
        },
        "frame_id": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.gnss.list`

List application-visible GNSS receivers with stable identity metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `804a1f4a8117186940ee085d9fdacc38e9c7943e2975a82788bcb611e96010ba`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "status": {
            "type": "string"
          },
          "health": {
            "type": "string"
          },
          "frame_id": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.gnss.sample`

Collect bounded application-normalized position samples from one GNSS route.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `BOUNDED_STREAM`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `ea9eb8b490d9c1f7cf05c3d53790d170241bb7ca34c8f298a7ef257469c1e494`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string"
    },
    "duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 30
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 1000000
    }
  },
  "required": [
    "duration_s",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "status",
    "observed_at",
    "truncated",
    "items"
  ],
  "additionalProperties": false
}
```

## `app.gnss.status`

Read fix availability and receiver health without returning a position sample.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `cae0e43f5266d6b6cba646b3ec75aa43d9ca7df53f99023269385101875dc523`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.gripper.status`

Read gripper readiness, opening state, and bounded health metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `65fc2daa1d22f4b9b2869eef246cc7e7095af4caa018142422a4f060cc6c4ff6`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.imu.calibration.status`

Read calibration availability, identity, and age for one inertial unit.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `1149975c8eb054edcf87650a716f87e638a2c3f5a48b3698325dec16ee5089cc`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.imu.inspect`

Inspect identity, frame, ranges, and bounded metadata for one inertial unit.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `70173f03cfe85bfbe983ef11d21b77eb97253a889e4c696db6b410a411480e8e`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "status": {
          "type": "string"
        },
        "health": {
          "type": "string"
        },
        "frame_id": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.imu.list`

List application-visible inertial units with stable identity and frame metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `d3fba08dccd9b0012d4abc9fe30463b586789635bd4de43ff96d74bc029157ef`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "status": {
            "type": "string"
          },
          "health": {
            "type": "string"
          },
          "frame_id": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.imu.sample`

Collect bounded application-normalized inertial samples from one IMU route.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `BOUNDED_STREAM`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `ded0cedcbf245048034dbac73c61951afff048d56936ddcefc498554a8d086be`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string"
    },
    "duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 30
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 1000000
    }
  },
  "required": [
    "duration_s",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "status",
    "observed_at",
    "truncated",
    "items"
  ],
  "additionalProperties": false
}
```

## `app.imu.status`

Read stream availability and health for one inertial measurement unit.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `3028942371dbd7c2077d18ec26ad0ba0253f6828e1292191a472903670e9fc7b`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.lidar.calibration.status`

Read calibration availability, identity, and age for one lidar.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `3a8f1accd584a5b615cb35de97170bb2074931af356891a83917f44d37e9368d`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.lidar.inspect`

Inspect identity, frame, scan geometry, and bounded metadata for one lidar.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `0db2cdac684e3cb9ae1d891ab84b772e92b8f771a70d15532489f68df45a5dd2`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "status": {
          "type": "string"
        },
        "health": {
          "type": "string"
        },
        "frame_id": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.lidar.list`

List application-visible lidars with stable identity and frame metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `7bfed839997b2e409e000bdbe08a811dfc5d4a6c69c9cb84858207a9a3ad72ce`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "status": {
            "type": "string"
          },
          "health": {
            "type": "string"
          },
          "frame_id": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.lidar.snapshot`

Capture or reference one bounded application-normalized lidar observation.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `6fd90eb65fe95dd7dcdf4d3c82ed3f78cfd4a1c7fe0f7a20a3082c2b32d38d3c`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 100000000
    }
  },
  "required": [
    "id",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "media_type": {
      "type": "string"
    },
    "frame_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "artifact_ref",
    "media_type",
    "frame_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.lidar.status`

Read stream availability and health for one application-visible lidar.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `be239e77a77879997c5aa4ca62d7fcc1f3ae3569f702693b89eab941ea971ab9`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.localization.initialize`

Request localization initialization from one bounded pose hypothesis.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `c3b3f65f9ffb73fd21a4ada944940cf9298cd12ff85bd499706f9292253a84d2`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "map_id": {
      "type": "string",
      "minLength": 1
    },
    "frame_id": {
      "type": "string",
      "minLength": 1
    },
    "x_m": {
      "type": "number"
    },
    "y_m": {
      "type": "number"
    },
    "yaw_rad": {
      "type": "number"
    },
    "covariance": {
      "type": "array",
      "items": {
        "type": "number"
      },
      "minItems": 36,
      "maxItems": 36
    }
  },
  "required": [
    "map_id",
    "frame_id",
    "x_m",
    "y_m",
    "yaw_rad"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.localization.pose`

Read one timestamped robot pose in the declared localization frame.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `c280e2e721df37831a7a74223f5918b3ed037905d53f0d26cd7ba287fe87d8a4`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "frame_id": {
      "type": "string"
    },
    "child_frame_id": {
      "type": "string"
    },
    "x_m": {
      "type": "number"
    },
    "y_m": {
      "type": "number"
    },
    "z_m": {
      "type": "number"
    },
    "orientation_x": {
      "type": "number"
    },
    "orientation_y": {
      "type": "number"
    },
    "orientation_z": {
      "type": "number"
    },
    "orientation_w": {
      "type": "number"
    },
    "timestamp": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "frame_id",
    "x_m",
    "y_m",
    "orientation_x",
    "orientation_y",
    "orientation_z",
    "orientation_w",
    "timestamp",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.localization.quality`

Read normalized localization quality and the frame to which it applies.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `855f0f807893b9645caeab8463b9205980e61bd7033d4351da60c2b45f4d241f`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "quality": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "frame_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "quality",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.localization.relocalize`

Request bounded global relocalization against one selected map without commanding motion.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `f8701f5c1baa8fb6743e4e7aa0ed3c0eb5099fcc7bef362531e862d5fbda2bfd`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "map_id": {
      "type": "string",
      "minLength": 1
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 60
    }
  },
  "required": [
    "map_id",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.localization.reset`

Request reset of application localization to an explicitly uninitialized state.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `c5929325a6c55a3a0de598a890c2c6dafce5a805ed488d677c8f467a1eceecfe`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.localization.status`

Read localization readiness and bounded quality metadata without changing state.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `1967add5892c7df8f374c608bb965654931c672f97bf903ab1f00e824d388a30`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "localized": {
      "type": "boolean"
    },
    "quality": {
      "type": "number",
      "minimum": 0,
      "maximum": 1
    },
    "frame_id": {
      "type": "string"
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.manipulation.plan`

Compute a bounded manipulation plan without executing actuator commands.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `d2b6db540f177347bfe184b2aecefba2391feea028f415d960563df354b5d999`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "group": {
      "type": "string",
      "minLength": 1
    },
    "goal": {
      "type": "object",
      "properties": {
        "representation": {
          "type": "string",
          "enum": [
            "joint",
            "pose",
            "named"
          ]
        },
        "value_json": {
          "type": "string",
          "minLength": 1
        },
        "frame_id": {
          "type": "string"
        }
      },
      "required": [
        "representation",
        "value_json"
      ],
      "additionalProperties": false
    },
    "planner_id": {
      "type": "string"
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 10000000
    }
  },
  "required": [
    "group",
    "goal",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "plan_id": {
      "type": "string"
    },
    "group": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "summary": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "plan_id",
    "group",
    "artifact_ref",
    "summary",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.manipulation.status`

Read manipulator readiness, control mode, and bounded health metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `9633a8acb55ed1bc1e7b6cafed54aa9074eea8852133c910202a50ed59553f6d`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.map.clear`

Request clearing of one map resource without deleting its stable identity.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `db4c63c79285ef89df7a8d1958c50e13ad4baed33f8d3cf7b193fe8842e2f31d`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "map_id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "map_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "map_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "map_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.map.create`

Create one inactive empty map record without starting mapping or robot motion.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `e724ca8e092b1a85427ad4490499b40ee2146549fdeb90a629bfe54561ce3ec2`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128
    },
    "frame_id": {
      "type": "string",
      "minLength": 1
    },
    "resolution_m": {
      "type": "number",
      "minimum": 0.001,
      "maximum": 1
    }
  },
  "required": [
    "name",
    "frame_id",
    "resolution_m"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "map_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "map_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.map.export`

Export one bounded map artifact without changing the active map or target state.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `fe8da03642d0ff77fbd2f40ec58e86f2fe753296c0259e3ccd17c605744ff16e`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "map_id": {
      "type": "string",
      "minLength": 1
    },
    "format": {
      "type": "string",
      "enum": [
        "native",
        "occupancy_grid",
        "geojson"
      ]
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 100000000
    }
  },
  "required": [
    "map_id",
    "format",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "map_id": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "media_type": {
      "type": "string"
    },
    "bytes": {
      "type": "integer",
      "minimum": 0
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "map_id",
    "artifact_ref",
    "media_type",
    "bytes",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.map.import`

Import one digest-pinned protected artifact as a new inactive map record.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `20a3da9414958ff5083685d654e9ba77f5b1a9748943f9590ddb182f48095a6c`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 128
    },
    "format": {
      "type": "string",
      "enum": [
        "ros_yaml",
        "nav2",
        "occupancy_grid",
        "vendor"
      ]
    },
    "artifact_ref": {
      "type": "string",
      "minLength": 12
    },
    "artifact_sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100000000
    }
  },
  "required": [
    "name",
    "format",
    "artifact_ref",
    "artifact_sha256",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "map_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "map_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.map.inspect`

Read bounded metadata for the active or selected two-dimensional map.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `f11fb1985eb891ca0a87125608b1359d0c962bcfdfe436bbea284dc6e4197251`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "map_id": {
      "type": "string"
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "map_id": {
      "type": "string"
    },
    "frame_id": {
      "type": "string"
    },
    "resolution_m": {
      "type": "number",
      "minimum": 0
    },
    "width": {
      "type": "integer",
      "minimum": 0
    },
    "height": {
      "type": "integer",
      "minimum": 0
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.map.list`

List bounded identifiers and metadata for maps visible to the application.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `a39851f7bfa16d261f295fa5ea0d4bb4f0a2cbeb9c960588441726a014d5e985`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "status": {
            "type": "string"
          },
          "health": {
            "type": "string"
          },
          "frame_id": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.map.load`

Request activation of one existing internal map without starting navigation or motion.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `769c8e4321ce7ca82d136e2eb8ead08cec341dd647ef4439305b967a9c32c01b`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "map_id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "map_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "map_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "map_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.map.save`

Request persistence of one application map into the internal map repository.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `7043e54e06b7cfe9a270e012fce3342a4e9d1a9c1df167af656a0f80a42c056f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "map_id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "map_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "map_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "map_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.navigation.costmap.inspect`

Inspect bounded costmap metadata and a protected artifact reference.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `feac0abe8822fff0d24a32af842c32d36e40111bd625b6948f4c970c1e6669e9`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 100000000
    }
  },
  "required": [
    "id",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "frame_id": {
      "type": "string"
    },
    "resolution_m": {
      "type": "number",
      "minimum": 0
    },
    "width": {
      "type": "integer",
      "minimum": 0
    },
    "height": {
      "type": "integer",
      "minimum": 0
    },
    "artifact_ref": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "frame_id",
    "resolution_m",
    "width",
    "height",
    "artifact_ref",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.navigation.path.inspect`

Inspect one bounded navigation path with explicit frame and metric coordinates.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `34bfcb3dad7b5f6a306a3b02ec1071d8b146f85a07cbb3fc78298accd42b204f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "max_points": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 10000000
    }
  },
  "required": [
    "id",
    "max_points",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "frame_id": {
      "type": "string"
    },
    "points": {
      "type": "array",
      "maxItems": 5000,
      "items": {
        "type": "object",
        "properties": {
          "x_m": {
            "type": "number"
          },
          "y_m": {
            "type": "number"
          },
          "z_m": {
            "type": "number"
          },
          "yaw_rad": {
            "type": "number"
          }
        },
        "required": [
          "x_m",
          "y_m"
        ],
        "additionalProperties": false
      }
    },
    "truncated": {
      "type": "boolean"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "frame_id",
    "points",
    "truncated",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.navigation.plan`

Compute a bounded navigation plan without starting or authorizing robot motion.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `ad692d32ec5a57742dfb815c00bf40a16d173ff8ef8cae3dbda94ca25723ea68`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "start": {
      "type": "object",
      "properties": {
        "frame_id": {
          "type": "string"
        },
        "x_m": {
          "type": "number"
        },
        "y_m": {
          "type": "number"
        },
        "yaw_rad": {
          "type": "number"
        }
      },
      "required": [
        "frame_id",
        "x_m",
        "y_m",
        "yaw_rad"
      ],
      "additionalProperties": false
    },
    "goal": {
      "type": "object",
      "properties": {
        "frame_id": {
          "type": "string"
        },
        "x_m": {
          "type": "number"
        },
        "y_m": {
          "type": "number"
        },
        "yaw_rad": {
          "type": "number"
        }
      },
      "required": [
        "frame_id",
        "x_m",
        "y_m",
        "yaw_rad"
      ],
      "additionalProperties": false
    },
    "planner_id": {
      "type": "string"
    },
    "max_points": {
      "type": "integer",
      "minimum": 1,
      "maximum": 5000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 10000000
    }
  },
  "required": [
    "goal",
    "max_points",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "plan_id": {
      "type": "string"
    },
    "frame_id": {
      "type": "string"
    },
    "points": {
      "type": "array",
      "maxItems": 5000,
      "items": {
        "type": "object",
        "properties": {
          "x_m": {
            "type": "number"
          },
          "y_m": {
            "type": "number"
          },
          "yaw_rad": {
            "type": "number"
          }
        },
        "required": [
          "x_m",
          "y_m"
        ],
        "additionalProperties": false
      }
    },
    "truncated": {
      "type": "boolean"
    },
    "artifact_ref": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "plan_id",
    "frame_id",
    "points",
    "truncated",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.navigation.status`

Read navigation lifecycle, current activity, and bounded readiness metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `caf2ace79fae5304feadff92e4df9ebaced386313dc8e1c2095d120ff5ac5e9a`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.odometry.reset`

Request reset of the application odometry origin without commanding robot motion.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `0c16fd8ef8124f5de708250f12439a05fb0e222bd393e91eac259924a244f5b4`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "mode": {
      "type": "string",
      "enum": [
        "zero",
        "current_pose"
      ]
    }
  },
  "required": [
    "mode"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.odometry.sample`

Collect bounded application-normalized odometry samples with frame metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `BOUNDED_STREAM`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `3b9a0eed492163c2dfe05d6695d62f83e9113e694dfda270b25b0d45001a5603`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string"
    },
    "duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 30
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 1000000
    }
  },
  "required": [
    "duration_s",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "status",
    "observed_at",
    "truncated",
    "items"
  ],
  "additionalProperties": false
}
```

## `app.odometry.status`

Read odometry stream availability, frames, and bounded quality metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `e775b371b4ef791d4ae9ba29b5ea246e15568ed283f5a22dfb6a77bd1b3fb8e3`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.parameter.get`

Read one typed application parameter value through a stable parameter identity.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `bb26d5211b0cbbf6f442297f9b53b150abf45f5e244899b3aefc876f6656275d`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "value": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string"
        },
        "value_json": {
          "type": "string"
        }
      },
      "required": [
        "type",
        "value_json"
      ],
      "additionalProperties": false
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "value",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.parameter.inspect`

Inspect type, bounds, mutability, and metadata for one application parameter.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `206d96c98dc938cb9754c04af23b16c604a91c684ea028832ea0758228f974a2`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "status": {
          "type": "string"
        },
        "health": {
          "type": "string"
        },
        "frame_id": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.parameter.list`

List application parameter names and non-value metadata without returning values.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `c9dee69527ddb6c584f2bfc5485f7729bfb3719b04a6e0d0d28a2b1b57b8dfff`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "status": {
            "type": "string"
          },
          "health": {
            "type": "string"
          },
          "frame_id": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.parameter.rollback`

Request rollback of one parameter revision under a new execution-quiescence lease.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `true`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `eaa7bf42d9e5a9d9648dd6cadb4547f87aab4e007e3e68dffbfb15800376bd44`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "rollback_token": {
      "type": "string",
      "minLength": 12
    },
    "expected_current_revision": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id",
    "rollback_token",
    "expected_current_revision"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "revision": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "revision",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.parameter.set`

Request one typed application parameter update under an execution-quiescence lease.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `true`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `cbd1d219844a7d403d2b629dee2d2d91a9a0c0fea934f3297efa0ac5f078c398`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "value": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": [
            "boolean",
            "integer",
            "number",
            "string",
            "json"
          ]
        },
        "value_json": {
          "type": "string",
          "maxLength": 1000000
        }
      },
      "required": [
        "type",
        "value_json"
      ],
      "additionalProperties": false
    },
    "expected_current_revision": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id",
    "value",
    "expected_current_revision"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "revision": {
      "type": "string"
    },
    "rollback_token": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "revision",
    "rollback_token",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.parameter.validate`

Validate a typed application parameter candidate without setting its value.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `74b118b9f61384bcc9bce06516919e30686b29be20e1e74df8ce7297c57a55ce`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "value": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string"
        },
        "value_json": {
          "type": "string"
        }
      },
      "required": [
        "type",
        "value_json"
      ],
      "additionalProperties": false
    }
  },
  "required": [
    "id",
    "value"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "valid": {
      "type": "boolean"
    },
    "findings": {
      "type": "array",
      "maxItems": 100,
      "items": {
        "type": "string"
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "valid",
    "findings",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.regression.cancel`

Request ordinary cancellation of one target-bound regression run.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `3e9024319f3646c8c493f855e22ee7b9754f3fba5e00c8af01006fdd8e85be31`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "run_id": {
      "type": "string",
      "minLength": 1
    },
    "reason": {
      "type": "string",
      "maxLength": 512
    }
  },
  "required": [
    "run_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "run_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "run_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.regression.plan`

Compute a bounded regression-suite plan without scheduling or running tests.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `8291c9f4d16ed58cb8542ccfb4b28c99c19754398a707fdd290d5ae0156f302f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "suite_id": {
      "type": "string",
      "minLength": 1
    },
    "max_tests": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 10000000
    }
  },
  "required": [
    "suite_id",
    "max_tests",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "plan_id": {
      "type": "string"
    },
    "suite_id": {
      "type": "string"
    },
    "test_count": {
      "type": "integer",
      "minimum": 0
    },
    "artifact_ref": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "plan_id",
    "suite_id",
    "test_count",
    "artifact_ref",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.regression.result`

Read the bounded aggregate result document for one target-defined regression run.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `99533235a4055c14fefe92393af447d1a6c3bc3a11cc3548003573bb5e2de192`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "result": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "result",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.regression.run`

Submit one bounded regression-suite plan under external R3 authorization.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R3`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_PLAN, INTERLOCK_BLOCKED, BUSY, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `c0e75d912b858d227006414611956941e603b9e15c96b03723ac694840d0a3df`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "suite_id": {
      "type": "string",
      "minLength": 1
    },
    "plan_id": {
      "type": "string",
      "minLength": 1
    },
    "max_run_duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 86400
    }
  },
  "required": [
    "suite_id",
    "plan_id",
    "max_run_duration_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "run_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "run_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.regression.status`

Read lifecycle state and bounded progress metadata for one regression run.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `2534f0a8cce58efadf16a6d205be5cfb1d6cdfef76a01a8c821f3cabe0f9cf62`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.robot.discover`

Discover bounded application entrypoints and declared interfaces from supplied roots.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl app robot discover`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `7876ac2afb7c6ea6f4d2a6efcf1479601337bc61434176ec7d8a9c34f959e656`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "source_roots": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "layer": {
      "type": "string",
      "enum": [
        "application"
      ]
    },
    "status": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "errors": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "layer",
    "status",
    "data",
    "warnings",
    "errors",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.robot.health`

Read the aggregated application health and bounded supporting details.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `3d3e5d0757295d9b6c9e3f23e387850c55c57a66d5687a0ef543d4fcc322c5e8`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.robot.status`

Read the target robot application lifecycle state without changing it.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `44d5d08599cd23cb75fe8d608466413788d2d67653548b446ae594b5c96fd736`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.safety.approval.status`

Read whether required operational safety approval is currently present.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `df6f9d24ed96bc9d9615c9037aa3052272e5ed34163c9002358531ad82b57ee1`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.safety.emergency_stop`

Request the target safety controller to enter its emergency-stop state.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R3`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, NOT_AUTHORIZED, PRECONDITION_FAILED, OPERATION_FAILED`
- Contract SHA-256: `5c8e0c5766a3034a9838f6122aba36fc852263bfc890af3857fbc95cac6563e4`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "stop_state": {
      "type": "string"
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.safety.interlocks.inspect`

Read bounded configured interlocks and their observed states.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `b06d01cb142af1e556ad445862b5d532df1f5337fffc16ed50e9958244688cdc`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "data",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.safety.limits.inspect`

Read bounded configured motion and operating limits without changing them.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `615cc5f655effa1de9682ee514c3a81408f687920c899a1b005a4941117131ea`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "data",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.safety.protective_stop`

Request the target safety controller to enter a protective-stop state.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R3`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, NOT_AUTHORIZED, PRECONDITION_FAILED, OPERATION_FAILED`
- Contract SHA-256: `829cad7373b896627c579e6c2f8189e23ca0db37d17c26f0af356bdd0f94582e`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "stop_state": {
      "type": "string"
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.safety.status`

Read aggregated stop, interlock, and safety-controller state.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `66cba1eadfa64450c14bb2fed846c5b3328d0806acde1822196bec542ef9508e`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.safety.stop.clear`

Request clearance of a previously established target safety stop state.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R3`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, NOT_AUTHORIZED, PRECONDITION_FAILED, OPERATION_FAILED`
- Contract SHA-256: `7cf56516c9d5343f70731b6a31a6f4b9c10c6f2692b67d988711b3f3ceee56a1`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "stop_state": {
      "type": "string"
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.safety.zones.inspect`

Read bounded configured safety-zone geometry without changing it.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `44c4642687d75f9e66ea9baf092f7962bae39bb791996f9b858f1971015d9666`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "data",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.state.snapshot`

Read one bounded application state snapshot without changing target state.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `05cc82ccf040152d0f8856f4cf06acee012f8d26559bc2c27088412b0d2fa4b2`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "state": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "state",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.state.watch`

Watch bounded application state observations within explicit resource limits.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `BOUNDED_STREAM`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `bf84ef54eaf86e5276a5ac8b284d3299b36e9885bd94e1083cd53769ab1da5ba`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string"
    },
    "duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 30
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 1000000
    }
  },
  "required": [
    "duration_s",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "status",
    "observed_at",
    "truncated",
    "items"
  ],
  "additionalProperties": false
}
```

## `app.task.cancel`

Request ordinary cancellation of one target-bound task run.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `ebe41931d6089b83ea3cdd6f5ea594b3231a994af4157486f0a23f1a0ec5a630`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "run_id": {
      "type": "string",
      "minLength": 1
    },
    "reason": {
      "type": "string",
      "maxLength": 512
    }
  },
  "required": [
    "run_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "run_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "run_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.task.describe`

Describe inputs, lifecycle, and bounded metadata for one target-defined task.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `60b7abf9aa66e37dbe7bd099698b935444440424cc231553694b758f43676660`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "status": {
          "type": "string"
        },
        "health": {
          "type": "string"
        },
        "frame_id": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.task.list`

List target-defined task types and active task instances with stable identifiers.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `cfda88e7b83622a2f17ff4302c212e152802a2802fcf4bbb05ef073a3fdea219`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "status": {
            "type": "string"
          },
          "health": {
            "type": "string"
          },
          "frame_id": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.task.result`

Read the bounded target-defined result document for one completed task instance.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `5fbc572358d278410e092fed85014426151cfb21b13c7086f48c35d558dc63fe`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "result": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "result",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.task.start`

Submit one bounded target-defined task run under external R3 authorization.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R3`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_PLAN, INTERLOCK_BLOCKED, BUSY, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `fbb41bdd3268f404eb6ef4c56fc26ea9c1b32c48115dadf9c16188ca75323aac`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "task_id": {
      "type": "string",
      "minLength": 1
    },
    "input_set_id": {
      "type": "string",
      "minLength": 1
    },
    "execution_profile_id": {
      "type": "string",
      "minLength": 1
    },
    "max_run_duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 86400
    }
  },
  "required": [
    "task_id",
    "input_set_id",
    "execution_profile_id",
    "max_run_duration_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "run_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "run_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.task.status`

Read lifecycle state and bounded progress metadata for one task instance.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `f5a060a38d5f351ab649f60c2c15990bcee1c93e33ad7c3de585f768902e76f7`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.telemetry.export`

Export bounded application telemetry to an artifact without changing the target.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `6de2bcc7352be7d7283d29c28241a170294661a91da058fe898127ee75efabe5`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "since": {
      "type": "string"
    },
    "until": {
      "type": "string"
    },
    "format": {
      "type": "string",
      "enum": [
        "json",
        "jsonl",
        "csv"
      ]
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 100000000
    }
  },
  "required": [
    "format",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "media_type": {
      "type": "string"
    },
    "bytes": {
      "type": "integer",
      "minimum": 0
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "artifact_ref",
    "media_type",
    "bytes",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.telemetry.snapshot`

Read a bounded set of named application telemetry observations with units.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `7febbe20318b3e1b588015b34ef89167b3ebdaa7bd9bee2958adab33f701fb59`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "names": {
      "type": "array",
      "maxItems": 256,
      "items": {
        "type": "string"
      }
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 10000000
    }
  },
  "required": [
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "metrics": {
      "type": "array",
      "maxItems": 1000,
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value_json": {
            "type": "string"
          },
          "unit": {
            "type": "string"
          },
          "observed_at": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value_json",
          "observed_at"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "metrics",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.telemetry.watch`

Watch bounded application telemetry within explicit time, item, and byte limits.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `BOUNDED_STREAM`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `a919ded06f4bb596ded1833068f9c9b7d31716209380bc8bdcfe2e86ea19a227`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string"
    },
    "duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 30
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 1000000
    }
  },
  "required": [
    "duration_s",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "status",
    "observed_at",
    "truncated",
    "items"
  ],
  "additionalProperties": false
}
```

## `app.teleop.velocity`

Submit a bounded planar base velocity command in base_link coordinates.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R3`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, NOT_AUTHORIZED, PRECONDITION_FAILED, OPERATION_FAILED`
- Contract SHA-256: `2e779398303a5f810f7c328a6f20af4d82ccbb4513eaa626257be3e8e33e9661`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "linear_x_mps": {
      "type": "number"
    },
    "angular_z_radps": {
      "type": "number"
    }
  },
  "required": [
    "linear_x_mps",
    "angular_z_radps"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    }
  },
  "required": [
    "status"
  ],
  "additionalProperties": false
}
```

## `app.test.cancel`

Request ordinary cancellation of one target-bound test run.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `60edabf0d07b75a056cb4e63c035ae469311f69e5d343dd03d5b3b5a0379238d`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "run_id": {
      "type": "string",
      "minLength": 1
    },
    "reason": {
      "type": "string",
      "maxLength": 512
    }
  },
  "required": [
    "run_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "run_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "run_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.test.describe`

Describe inputs, scope, and bounded metadata for one target-defined test.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `43d8478f1e363b94336f80ca78110f007c3297286b418cddbc57ebe8155e9330`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "status": {
          "type": "string"
        },
        "health": {
          "type": "string"
        },
        "frame_id": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.test.evidence`

List bounded artifact references associated with one target-defined test run.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `f67ae71dade76213a6436f898c929082083498a1bb29d66d605cf3deae058da0`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "artifacts": {
      "type": "array",
      "maxItems": 256,
      "items": {
        "type": "object",
        "properties": {
          "artifact_ref": {
            "type": "string",
            "minLength": 1
          },
          "media_type": {
            "type": "string"
          },
          "observed_at": {
            "type": "string"
          }
        },
        "required": [
          "artifact_ref"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "artifacts",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.test.list`

List target-defined tests with stable identifiers and availability metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `759bf06cac632c9afb3e122a73601b4df356366035de4f0f438cc7e4b9c6bf2e`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "status": {
            "type": "string"
          },
          "health": {
            "type": "string"
          },
          "frame_id": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.test.plan`

Compute a bounded test plan artifact without scheduling or running the test.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `19924a75ac4f2db893af602dd4f000317db06f87773ed0eb90c618352a0b11d1`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "test_id": {
      "type": "string",
      "minLength": 1
    },
    "inputs_json": {
      "type": "string"
    },
    "max_cases": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 10000000
    }
  },
  "required": [
    "test_id",
    "max_cases",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "plan_id": {
      "type": "string"
    },
    "test_id": {
      "type": "string"
    },
    "case_count": {
      "type": "integer",
      "minimum": 0
    },
    "artifact_ref": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "plan_id",
    "test_id",
    "case_count",
    "artifact_ref",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.test.result`

Read the bounded verdict and result document for one target-defined test run.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `e7b2c4a2eaa583dbda543535d16f1c553ea177320b08e944264fa58668a6adee`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "result": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "result",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.test.run`

Submit one bounded test plan under external R3 authorization.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R3`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_PLAN, INTERLOCK_BLOCKED, BUSY, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `9bf2c3ad298ec6fbee63a5b71538cb5de79cdb5ad9b189156e4cd29166d85b22`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "test_id": {
      "type": "string",
      "minLength": 1
    },
    "plan_id": {
      "type": "string",
      "minLength": 1
    },
    "max_run_duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 86400
    }
  },
  "required": [
    "test_id",
    "plan_id",
    "max_run_duration_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "run_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "run_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.test.status`

Read lifecycle state and bounded progress metadata for one test run.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `fc7aabd22e243732bc722ca29a030055c66ccecd17d8fb718b45e90e0d323904`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.tuning.baseline.create`

Create an immutable tuning baseline from existing parameter and evidence references.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `5d37ec07039e11fab1a2854b8fb06d9eae869947224257b7acbad28aaf09e05c`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 256
    },
    "parameter_snapshot_id": {
      "type": "string",
      "minLength": 1
    },
    "evidence_set_id": {
      "type": "string",
      "minLength": 1
    },
    "metric_set_id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name",
    "parameter_snapshot_id",
    "evidence_set_id",
    "metric_set_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "baseline_id": {
      "type": "string"
    },
    "revision": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "baseline_id",
    "revision",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.tuning.candidate.create`

Create an inactive tuning candidate from a digest-pinned bounded patch artifact.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `2774804daae567cd64531b2709ff2a5f4de4599faffe879eda3c38f8af5e67a2`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "baseline_id": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1,
      "maxLength": 256
    },
    "artifact_ref": {
      "type": "string",
      "minLength": 12
    },
    "artifact_sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64
    },
    "format": {
      "type": "string",
      "enum": [
        "json"
      ]
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10000000
    }
  },
  "required": [
    "baseline_id",
    "name",
    "artifact_ref",
    "artifact_sha256",
    "format",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "candidate_id": {
      "type": "string"
    },
    "revision": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "candidate_id",
    "revision",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.tuning.candidate.evaluate`

Evaluate one tuning candidate against existing bounded evidence without applying or running it.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `8f6b8826c78891fa3a1d4b314681d271764473dbf3af9016fa9097251033f4e1`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "candidate_id": {
      "type": "string",
      "minLength": 1
    },
    "baseline_id": {
      "type": "string",
      "minLength": 1
    },
    "metric_set_id": {
      "type": "string",
      "minLength": 1
    },
    "max_metrics": {
      "type": "integer",
      "minimum": 1,
      "maximum": 256
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 60
    }
  },
  "required": [
    "candidate_id",
    "baseline_id",
    "metric_set_id",
    "max_metrics",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "candidate_id": {
      "type": "string"
    },
    "baseline_id": {
      "type": "string"
    },
    "verdict": {
      "type": "string",
      "enum": [
        "BETTER",
        "EQUIVALENT",
        "WORSE",
        "INCONCLUSIVE"
      ]
    },
    "metrics": {
      "type": "array",
      "maxItems": 256,
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value": {
            "type": "number"
          },
          "baseline_value": {
            "type": "number"
          },
          "unit": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value"
        ],
        "additionalProperties": false
      }
    },
    "findings": {
      "type": "array",
      "maxItems": 100,
      "items": {
        "type": "string"
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "candidate_id",
    "baseline_id",
    "verdict",
    "metrics",
    "findings",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.tuning.commit`

Request activation of one evaluated candidate under an execution-quiescence lease.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `true`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `766dc576f57088f6d011ffd04fb024c37de2da4e892230c1bddc6c35536ded16`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "candidate_id": {
      "type": "string",
      "minLength": 1
    },
    "evaluation_id": {
      "type": "string",
      "minLength": 1
    },
    "expected_active_revision": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "candidate_id",
    "evaluation_id",
    "expected_active_revision"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "commit_id": {
      "type": "string"
    },
    "revision": {
      "type": "string"
    },
    "rollback_token": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "commit_id",
    "revision",
    "rollback_token",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.tuning.rollback`

Request rollback of a tuning commit under a new execution-quiescence lease.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `true`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `edd3b13b89d58c520ab2df6bf339c33b3b3c17122d09ba8523f71db27b27f75c`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "commit_id": {
      "type": "string",
      "minLength": 1
    },
    "rollback_token": {
      "type": "string",
      "minLength": 12
    },
    "expected_active_revision": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "commit_id",
    "rollback_token",
    "expected_active_revision"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "commit_id": {
      "type": "string"
    },
    "revision": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "commit_id",
    "revision",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `app.tuning.status`

Read lifecycle state and bounded metadata for the active tuning workflow.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `app` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `776530585236c9b5809731f7b58051f28f87249d36c5f04c88735133326b8099`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "details": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `checkpoint.create`

Create an immutable Rolo control-plane state anchor without changing target state.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `control` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, CONFLICT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `a4062da2481aecdde201e199976d89a98261cf5d4f0c37207c6bf121cf840cd9`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "episode_id": {
      "type": "string",
      "minLength": 1
    },
    "label": {
      "type": "string",
      "minLength": 1,
      "maxLength": 256
    },
    "scope": {
      "type": "array",
      "minItems": 1,
      "maxItems": 4,
      "items": {
        "type": "string",
        "enum": [
          "state_graph",
          "workflow_progress",
          "configuration_refs",
          "evidence_index"
        ]
      }
    }
  },
  "required": [
    "episode_id",
    "label",
    "scope"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "checkpoint_id": {
      "type": "string"
    },
    "revision": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "checkpoint_id",
    "revision",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `checkpoint.list`

List bounded Rolo control-plane checkpoint metadata without resolving saved state.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `control` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_INPUT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `b8c9383d0eb6683c68c250ea6b4f0a004b1a0b3530a901d7370d1369babeea85`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "episode_id": {
      "type": "string"
    },
    "cursor": {
      "type": "string"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    }
  },
  "required": [
    "limit"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "maxItems": 1000,
      "items": {
        "type": "object",
        "properties": {
          "checkpoint_id": {
            "type": "string"
          },
          "episode_id": {
            "type": "string"
          },
          "label": {
            "type": "string"
          },
          "revision": {
            "type": "string"
          },
          "created_at": {
            "type": "string"
          }
        },
        "required": [
          "checkpoint_id",
          "episode_id",
          "revision",
          "created_at"
        ],
        "additionalProperties": false
      }
    },
    "next_cursor": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `checkpoint.restore`

Restore saved Rolo control-plane metadata without applying target state or resuming execution.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `control` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, CONFLICT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `1b602711e252fc95d245fce524f3df3dc96043d82b38d655c919a71382fa9cce`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "checkpoint_id": {
      "type": "string",
      "minLength": 1
    },
    "expected_current_revision": {
      "type": "string",
      "minLength": 1
    },
    "scope": {
      "type": "array",
      "minItems": 1,
      "maxItems": 4,
      "items": {
        "type": "string",
        "enum": [
          "state_graph",
          "workflow_progress",
          "configuration_refs",
          "evidence_index"
        ]
      }
    }
  },
  "required": [
    "checkpoint_id",
    "expected_current_revision",
    "scope"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "checkpoint_id": {
      "type": "string"
    },
    "revision": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "checkpoint_id",
    "revision",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `episode.export`

Export one bounded episode manifest and artifact index without copying artifact contents.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `control` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_INPUT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `56d90270e369b875d0a850d57fa5b9eafdeca896b3445260c8f6f540d9603d1f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "episode_id": {
      "type": "string",
      "minLength": 1
    },
    "format": {
      "type": "string",
      "enum": [
        "json",
        "jsonl"
      ]
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 100000000
    }
  },
  "required": [
    "episode_id",
    "format",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "episode_id": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "media_type": {
      "type": "string"
    },
    "bytes": {
      "type": "integer",
      "minimum": 0
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "episode_id",
    "artifact_ref",
    "media_type",
    "bytes",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `episode.inspect`

Read one bounded episode manifest with event metadata and artifact references only.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `control` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_INPUT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `2fec7f854e4472fc2880929adc7070904b7dc368045773281da6d789468e5f7c`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "episode_id": {
      "type": "string",
      "minLength": 1
    },
    "max_events": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10000
    },
    "max_artifacts": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 10000000
    }
  },
  "required": [
    "episode_id",
    "max_events",
    "max_artifacts",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "episode_id": {
      "type": "string"
    },
    "state": {
      "type": "string"
    },
    "started_at": {
      "type": "string"
    },
    "ended_at": {
      "type": "string"
    },
    "events": {
      "type": "array",
      "maxItems": 10000,
      "items": {
        "type": "object",
        "properties": {
          "event_id": {
            "type": "string"
          },
          "type": {
            "type": "string"
          },
          "occurred_at": {
            "type": "string"
          },
          "source": {
            "type": "string"
          }
        },
        "required": [
          "event_id",
          "type",
          "occurred_at"
        ],
        "additionalProperties": false
      }
    },
    "artifacts": {
      "type": "array",
      "maxItems": 1000,
      "items": {
        "type": "object",
        "properties": {
          "artifact_ref": {
            "type": "string"
          },
          "media_type": {
            "type": "string"
          },
          "observed_at": {
            "type": "string"
          }
        },
        "required": [
          "artifact_ref"
        ],
        "additionalProperties": false
      }
    },
    "truncated": {
      "type": "boolean"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "episode_id",
    "state",
    "started_at",
    "events",
    "artifacts",
    "truncated",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `episode.list`

List bounded episode metadata without returning event payloads or artifact contents.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `control` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_INPUT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `fb91ed11d0fd50b28ab74cb1a327e8672aab59dbffe4f59f61b8f68b6dc1dab5`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "since": {
      "type": "string"
    },
    "until": {
      "type": "string"
    },
    "state": {
      "type": "string"
    },
    "cursor": {
      "type": "string"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    }
  },
  "required": [
    "limit"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "maxItems": 1000,
      "items": {
        "type": "object",
        "properties": {
          "episode_id": {
            "type": "string"
          },
          "state": {
            "type": "string"
          },
          "started_at": {
            "type": "string"
          },
          "ended_at": {
            "type": "string"
          },
          "task_ref": {
            "type": "string"
          }
        },
        "required": [
          "episode_id",
          "state",
          "started_at"
        ],
        "additionalProperties": false
      }
    },
    "next_cursor": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `evidence.resolve`

Resolve one bounded discovery evidence reference and return metadata only.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `control` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `5s`
- Canonical CLI template: `robotctl adapt evidence resolve {reference} --robot {robot_id}`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `c970444abe7953f2959d405a54a11b9f21d1b10b343d5342e6074fec25eb3ba8`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "reference": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "reference"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "reference": {
      "type": "string"
    },
    "resolved_path": {
      "type": "string"
    },
    "authority": {
      "type": "string"
    },
    "kind": {
      "type": "string"
    },
    "size_bytes": {
      "type": "integer",
      "minimum": 0
    },
    "sha256": {
      "type": "string"
    }
  },
  "required": [
    "reference",
    "resolved_path",
    "authority",
    "kind"
  ],
  "additionalProperties": false
}
```

## `hw.actuator.inspect`

Inspect identity, model, limits, and bounded metadata for one actuator.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `97878a537f1d4f1b2f053cc969a220e1373d719ddb2069001dbb14de036fc57c`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "vendor": {
          "type": "string"
        },
        "model": {
          "type": "string"
        },
        "serial": {
          "type": "string"
        },
        "health": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.actuator.list`

List actuators with stable identity, model, and declared health metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `7a97cb14384390bfebaeeb7b159872e4ac66b955c1152191ef4ab5d5bd568458`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "vendor": {
            "type": "string"
          },
          "model": {
            "type": "string"
          },
          "serial": {
            "type": "string"
          },
          "health": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.actuator.status`

Read health and bounded diagnostic metrics for one actuator.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `7e811b3c1f6dd05131e9a5c461deb2c865505d861aa2485ac7921e0b05ad445e`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "metrics": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value": {
            "type": "number"
          },
          "unit": {
            "type": "string"
          },
          "timestamp": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value",
          "unit"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "metrics",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.bus.inspect`

Inspect identity, type, topology, and bounded metadata for one hardware bus.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `8e5f0f4aa8a30feb749e33eac8d8dd3195475d2c59a43e9daf190ff6f4dbf37b`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "vendor": {
          "type": "string"
        },
        "model": {
          "type": "string"
        },
        "serial": {
          "type": "string"
        },
        "health": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.bus.list`

List hardware buses with stable identity, type, and declared health metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `2575780c3ce4aff6fe4c3a192e47d640f16e173c69499bf1519d58322ce4d1d7`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "vendor": {
            "type": "string"
          },
          "model": {
            "type": "string"
          },
          "serial": {
            "type": "string"
          },
          "health": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.bus.scan`

Perform one bounded discovery scan on an explicit hardware bus.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R1`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `81779c981c8490a30d7fd3592434bceef086452b7d4bc76e3bb29d1b47ac760b`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "vendor": {
            "type": "string"
          },
          "model": {
            "type": "string"
          },
          "serial": {
            "type": "string"
          },
          "health": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.bus.statistics`

Read bounded traffic and error counters for one hardware bus.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `b81d4247f085424b27aacd553887af8ce89ae32431962f52fc15e531b0cd4dbe`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "metrics": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value": {
            "type": "number"
          },
          "unit": {
            "type": "string"
          },
          "timestamp": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value",
          "unit"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "metrics",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.bus.status`

Read health and bounded diagnostic metrics for one hardware bus.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `c5e5de974fee7b99369285f6f279ce770d778c68b2cb32a56dcfe797f6045f53`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "metrics": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value": {
            "type": "number"
          },
          "unit": {
            "type": "string"
          },
          "timestamp": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value",
          "unit"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "metrics",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.clock.status`

Read hardware clock source, offset, and synchronization metrics.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `d09dc5fd8218e22a988e370a6cd65b3ec4cbde39759af410efd2b3e2f942dc10`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "metrics": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value": {
            "type": "number"
          },
          "unit": {
            "type": "string"
          },
          "timestamp": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value",
          "unit"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "metrics",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.compute.inspect`

Inspect identity, model, and bounded metadata for one compute module.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `b84df63eb5d9067ccd081fb4f9bea33f930f546ee4f0d7c158ae717fe12be6bd`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "vendor": {
          "type": "string"
        },
        "model": {
          "type": "string"
        },
        "serial": {
          "type": "string"
        },
        "health": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.compute.list`

List compute modules with stable identity and declared health metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `2f73d01bca002a5f45959b8850fc736f192e27404cd3c8cdfa3e5ce011e4f3d5`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "vendor": {
            "type": "string"
          },
          "model": {
            "type": "string"
          },
          "serial": {
            "type": "string"
          },
          "health": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.compute.status`

Read health and numeric resource metrics for one compute module.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `746c3443a62030f2b91ad04bf2a1778ef85b06e3d9e22c8d9b67416dda42af58`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "metrics": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value": {
            "type": "number"
          },
          "unit": {
            "type": "string"
          },
          "timestamp": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value",
          "unit"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "metrics",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.firmware.inspect`

Inspect version, vendor, and bounded metadata for one firmware component.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `a7088d2f0b1141071d7fb3a8ff45933006e03479a4203c6eb93aed626167c932`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "vendor": {
          "type": "string"
        },
        "model": {
          "type": "string"
        },
        "serial": {
          "type": "string"
        },
        "health": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.firmware.list`

List firmware-bearing components and their reported versions.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `d973d3eef610a61a67a277f3ea200e71ec59a6b73399e6bc59c8d3cf032fd9fe`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "vendor": {
            "type": "string"
          },
          "model": {
            "type": "string"
          },
          "serial": {
            "type": "string"
          },
          "health": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.firmware.verify`

Verify reported firmware identity or digest without changing the component.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `7d6d4fde0756a2edc6d9e0d5dadf3b3abce7238b3dd116d5bbd1f2dd13f68441`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    },
    "expected_sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "verified": {
      "type": "boolean"
    },
    "observed_sha256": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "id",
    "verified",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.inventory.scan`

Perform bounded read-only inventory of compute, buses, and attached hardware.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl hw inventory scan`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `5a0bd33a98e9c5b667c3e29fd0f7e2dedb0969d68242b6714ec82871b6aa56e1`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "layer": {
      "type": "string",
      "enum": [
        "hw"
      ]
    },
    "status": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "errors": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "layer",
    "status",
    "data",
    "warnings",
    "errors",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.power.battery.status`

Read bounded battery charge, voltage, current, temperature, and health metrics.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `00b3dbaeaf4df3f9c8717b1f49fb11d168580ef61c7f12750291e815528bd903`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "metrics": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value": {
            "type": "number"
          },
          "unit": {
            "type": "string"
          },
          "timestamp": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value",
          "unit"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "metrics",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.power.rail.inspect`

Inspect identity, limits, and bounded metadata for one power rail.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `d09173b9a862dda4aae026f834ac9ca4559aa23377189d537176a0e48955571e`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "vendor": {
          "type": "string"
        },
        "model": {
          "type": "string"
        },
        "serial": {
          "type": "string"
        },
        "health": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.power.rail.list`

List controllable or observable power rails with stable identity metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `e77a2818851457241d183a41f9975dbef605f6f3be8d98691cf92ae262f62dbd`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "vendor": {
            "type": "string"
          },
          "model": {
            "type": "string"
          },
          "serial": {
            "type": "string"
          },
          "health": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.power.status`

Read overall robot power-source, voltage, current, and health metrics.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `4da57902922ed19a5498ba1d8f95349bfeafeac7ef5fb26a089ea2a0c9f66541`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "metrics": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value": {
            "type": "number"
          },
          "unit": {
            "type": "string"
          },
          "timestamp": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value",
          "unit"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "metrics",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.sensor.inspect`

Inspect identity, model, channels, and bounded metadata for one sensor.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `148b89a33c8baad88276ccb6992bbf4b7dfeef881507fe0a43bc8191201c7102`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "item": {
      "type": "object",
      "properties": {
        "id": {
          "type": "string"
        },
        "name": {
          "type": "string"
        },
        "vendor": {
          "type": "string"
        },
        "model": {
          "type": "string"
        },
        "serial": {
          "type": "string"
        },
        "health": {
          "type": "string"
        }
      },
      "required": [
        "id"
      ],
      "additionalProperties": true
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "item",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.sensor.list`

List sensors with stable identity, model, and declared health metadata.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `e23aa5cf3021020fc5f449b728dedb045e49382e2073d4b84ce2e7a4dce86995`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "id": {
            "type": "string"
          },
          "name": {
            "type": "string"
          },
          "vendor": {
            "type": "string"
          },
          "model": {
            "type": "string"
          },
          "serial": {
            "type": "string"
          },
          "health": {
            "type": "string"
          }
        },
        "required": [
          "id"
        ],
        "additionalProperties": true
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "items",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.sensor.read`

Read one bounded numeric sample set from an explicit sensor.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `f161dd4068b10798c7666697a326514379e84b3ca42cd18be42b55114e6a948a`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "metrics": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value": {
            "type": "number"
          },
          "unit": {
            "type": "string"
          },
          "timestamp": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value",
          "unit"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "metrics",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.sensor.status`

Read health and bounded diagnostic metrics for one sensor.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `eab48b87c4937fa5fa1be9c4a3e57702818e1eed40bc53f768d9d3d689cabb83`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "metrics": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value": {
            "type": "number"
          },
          "unit": {
            "type": "string"
          },
          "timestamp": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value",
          "unit"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "metrics",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.storage.status`

Read bounded capacity, wear, and health metrics for attached storage.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `ebed9d7a0918f007a6e96b406f8ee1759a48d3462c507e30340bd3a7a1bf167c`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "metrics": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value": {
            "type": "number"
          },
          "unit": {
            "type": "string"
          },
          "timestamp": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value",
          "unit"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "metrics",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `hw.thermal.status`

Read bounded temperatures, limits, and thermal health metrics.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `hw` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `a7aec29bece1ec720186ee30139ecb5c7445076f02f0472e2504f1c001fb14e2`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "id": {
      "type": "string"
    },
    "health": {
      "type": "string"
    },
    "metrics": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {
          "name": {
            "type": "string"
          },
          "value": {
            "type": "number"
          },
          "unit": {
            "type": "string"
          },
          "timestamp": {
            "type": "string"
          }
        },
        "required": [
          "name",
          "value",
          "unit"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "metrics",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.binary.describe`

Describe one binary statically without invoking its operational interface.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux binary describe {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `9ea47ebf61e901c0a8aca952db951b03e50f5fd0c23d9840513cd437c4d6fda9`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "path"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.binary.verify`

Compare one explicit binary against a caller-supplied SHA-256 digest.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux binary verify {path} --expected-sha256 {expected_sha256}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `7c14730c9ae5fe5290c55d478563dc1dfb2beb64e7036090121f06afd58b8820`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    },
    "expected_sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64
    }
  },
  "required": [
    "path",
    "expected_sha256"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.cli.probe`

Run bounded self-description arguments against one explicit executable.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux cli probe {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `8b3f7bafbd291c96bef43deba247cb7e3a1481048c2a8b5fa25beda1a5317315`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    },
    "args": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "maxItems": 8
    }
  },
  "required": [
    "path"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.config.apply`

Apply one digest-pinned configuration artifact to a discovered target resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_ARTIFACT, DIGEST_MISMATCH, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `1a62958e8cb819aa320ada769fa2e573e7b9e6aafbf2aa9e1244e97d2076c58f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "target_resource_id": {
      "type": "string",
      "minLength": 1
    },
    "artifact_ref": {
      "type": "string",
      "minLength": 12
    },
    "artifact_sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64
    },
    "format": {
      "type": "string",
      "enum": [
        "auto",
        "json",
        "yaml",
        "toml"
      ]
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100000000
    }
  },
  "required": [
    "target_resource_id",
    "artifact_ref",
    "artifact_sha256",
    "format",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "rollback_token": {
      "type": "string",
      "minLength": 12
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "rollback_token",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.config.diff`

Compare two policy-classified bounded configurations into a protected artifact.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `f48f6a86d720493153597d7479d61d0d142f8b56d59735e363a32f6de6ac3664`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "left_path": {
      "type": "string",
      "minLength": 1
    },
    "right_path": {
      "type": "string",
      "minLength": 1
    },
    "format": {
      "type": "string",
      "enum": [
        "auto",
        "json",
        "yaml",
        "toml"
      ]
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100000000
    }
  },
  "required": [
    "left_path",
    "right_path",
    "format",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "media_type": {
      "type": "string"
    },
    "bytes": {
      "type": "integer",
      "minimum": 0
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "artifact_ref",
    "media_type",
    "bytes",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.config.inspect`

Parse one policy-classified bounded configuration into a protected artifact.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `6d7d87d69607eee25fdb8f2f3439a859362f4b2985c82185d1e2ab8438fec466`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    },
    "format": {
      "type": "string",
      "enum": [
        "auto",
        "json",
        "yaml",
        "toml"
      ]
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100000000
    }
  },
  "required": [
    "path",
    "format",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "media_type": {
      "type": "string"
    },
    "bytes": {
      "type": "integer",
      "minimum": 0
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "artifact_ref",
    "media_type",
    "bytes",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.config.locate`

Locate bounded configuration candidates for a process or binary.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux config locate`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `df7c834f237b51af47d08755301d4054cc797a6286778b76d9a194319b79f1e6`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "process": {
      "type": "integer",
      "minimum": 1
    },
    "binary": {
      "type": "string",
      "minLength": 1
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.config.rollback`

Request rollback of one configuration target using its system-issued opaque token.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_ROLLBACK_TOKEN, TOKEN_EXPIRED, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `0c94e247e881f7e1772de8dd204563c60569733812d8c165dae8ae0612ce767f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "target_resource_id": {
      "type": "string",
      "minLength": 1
    },
    "rollback_token": {
      "type": "string",
      "minLength": 12
    }
  },
  "required": [
    "target_resource_id",
    "rollback_token"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.config.validate`

Validate one policy-classified bounded configuration without applying it.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `a89c05f09089c08b7c288c7eb6b0c4dc37923257758c9fb52aaa5b45f70b1a18`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    },
    "format": {
      "type": "string",
      "enum": [
        "auto",
        "json",
        "yaml",
        "toml"
      ]
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100000000
    }
  },
  "required": [
    "path",
    "format",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "valid": {
      "type": "boolean"
    },
    "findings": {
      "type": "array",
      "maxItems": 100,
      "items": {
        "type": "string"
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "valid",
    "findings",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.container.inspect`

Inspect one local container using an optional explicit runtime selection.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux container inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `73a5feabf1d7ad5783973def82e7dabf291e0c51260addfe8e9afe10a2282aaf`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    },
    "runtime": {
      "type": "string"
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.container.list`

List bounded metadata for local containers without changing their state.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux container list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `cfa2713eece87fa2ffaf844de4af3616fe4324a98141095a8cef7764d152ade7`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "runtime": {
      "type": "string"
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.container.logs`

Query bounded logs for one policy-classified stable container resource identity.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `41d9ff7e48ab130a0edde8eca1af8b9f5f3656a69dfcab1a479fd46d8b69fc86`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "since": {
      "type": "string"
    },
    "until": {
      "type": "string"
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100000000
    }
  },
  "required": [
    "resource_id",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "bytes": {
      "type": "integer",
      "minimum": 0
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    }
  },
  "required": [
    "status",
    "artifact_ref",
    "bytes",
    "observed_at",
    "truncated"
  ],
  "additionalProperties": false
}
```

## `linux.container.restart`

Request bounded restart of one discovered container resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `aabf4a1fcbed0a5c944049138fcf736b83aef844fe5101986038f32e0db6f697`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "runtime": {
      "type": "string",
      "enum": [
        "docker",
        "podman"
      ]
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 120
    }
  },
  "required": [
    "resource_id",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.container.start`

Request startup of one discovered container resource through its native runtime.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `4eea5871ca225e8e68126f49d0418fa8947a77967e3344752ceac230ca170c9a`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "runtime": {
      "type": "string",
      "enum": [
        "docker",
        "podman"
      ]
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 120
    }
  },
  "required": [
    "resource_id",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.container.stats`

Read one non-streaming resource snapshot from Docker or Podman.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux container stats`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `0eb276c74bb0db6e7d19f0c219d485907208905fc8e4849210287e8eaf3d3e7f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    },
    "runtime": {
      "type": "string",
      "enum": [
        "docker",
        "podman"
      ]
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.container.stop`

Request bounded stop of one discovered container resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `e18f858f180252e914d3ef7e6693834bf10c93c8678d343f75cf5af17e6cae16`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "runtime": {
      "type": "string",
      "enum": [
        "docker",
        "podman"
      ]
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 120
    }
  },
  "required": [
    "resource_id",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.file.hash`

Calculate a bounded SHA-256 digest for one explicit regular file.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux file hash {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `0090032988e2d8f1ef0578dc3878cd8737740b499463e49f200a3e1127690173`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "path"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.file.inspect`

Read metadata for one explicit filesystem entry without reading its content.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux file inspect {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `7982185a65b041bb13b8c0104c301511b7a65cb3052eeeb58c314294a02e8998`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "path"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.file.list`

List one directory level with a strict caller-controlled result bound.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux file list {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `5badb21f4c68960a74157e9f102ebcb1ff95b65fcac23b7ecfe4215669d5e74f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    }
  },
  "required": [
    "path"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.file.read`

Copy one policy-classified bounded file into a protected artifact without inline content.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `267c8d9148b2894cb3675eddc10efe1040ec540bd4c6d9afd8880c4c421b851c`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100000000
    }
  },
  "required": [
    "path",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "media_type": {
      "type": "string"
    },
    "bytes": {
      "type": "integer",
      "minimum": 0
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "artifact_ref",
    "media_type",
    "bytes",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.host.inventory`

Inventory host identity and available local control planes without mutation.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux host inventory`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `ac3c070fef7b97ee3d2e6662802b7b1777b01428999f1f67901fe47ec8349d49`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.host.reboot`

Request a bounded-delay reboot of the target host through its gated control plane.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `a71aa84ab91fa034e007903ab080cd253a03ca81dba3e9f1b5ef83a2565c334d`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "delay_s": {
      "type": "integer",
      "minimum": 0,
      "maximum": 300
    },
    "reason": {
      "type": "string"
    }
  },
  "required": [
    "delay_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.host.shutdown`

Request a bounded-delay shutdown of the target host through its gated control plane.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `0b4a32e6c6a77fa9427045edf58d8fcd4a01a86b71af437f3c593d3efaf802dd`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "delay_s": {
      "type": "integer",
      "minimum": 0,
      "maximum": 300
    },
    "reason": {
      "type": "string"
    }
  },
  "required": [
    "delay_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.host.status`

Read compact host identity, platform, architecture, and uptime status.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux host status`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `902b98067b616710e7201bff6ede51b15c98e23f1420ebfce45fa0e0800eca29`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.host.uptime`

Read elapsed seconds since the local host booted when supported.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux host uptime`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `a060740ffc3cc4fb4898ed1ac635109b12089918ad3dcc7a5a26bc9d680fb6bd`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.log.follow`

Follow one policy-classified log resource within explicit stream bounds.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `BOUNDED_STREAM`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `9e57e5f6a8d59de9e24b4dd5f38264a17330e2cdc9fc740cd59e6202a19cc12f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 30
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100000000
    }
  },
  "required": [
    "resource_id",
    "duration_s",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "bytes": {
      "type": "integer",
      "minimum": 0
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    }
  },
  "required": [
    "status",
    "artifact_ref",
    "bytes",
    "observed_at",
    "truncated"
  ],
  "additionalProperties": false
}
```

## `linux.log.query`

Query one policy-classified log resource within explicit result bounds.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `be462903e9127feb0aa06c9494fe197dcde6f3d7987c12430c319c1f60400b74`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "query": {
      "type": "string"
    },
    "since": {
      "type": "string"
    },
    "until": {
      "type": "string"
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100000000
    }
  },
  "required": [
    "resource_id",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "bytes": {
      "type": "integer",
      "minimum": 0
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    }
  },
  "required": [
    "status",
    "artifact_ref",
    "bytes",
    "observed_at",
    "truncated"
  ],
  "additionalProperties": false
}
```

## `linux.network.connections`

List bounded connection metadata and owning processes when available.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network connections`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `e0496517def5c14411846b3639d849140930be869c57e461e833bab75a9673e0`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.network.dns`

Read bounded local DNS resolver configuration metadata.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network dns`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `77ef7d805c5e508ff4567cab6d701dec2d57e0ef728d154005b94f0f9a6c3c4d`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.network.interfaces`

List bounded network-interface and assigned-address metadata.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network interfaces`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `2224a040971b208b60cb24c907b213b367d67bad42bd57637f8a83692b41f242`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.network.listeners`

List bounded local listening sockets and owning processes when available.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network listeners`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `19438cc677e473cbd6e4a692ab2ead5714f68d9e284ae720dab99a27589f7713`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.network.routes`

List bounded local routing-table entries without changing network state.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network routes`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `f41505e7aafff692fef54eb184f9c14822c1383d4547e80e5115252b17895148`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.network.statistics`

Read bounded per-interface packet, error, and byte counters.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network statistics`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `bf6a48e11088b6deada9fb74dc7d239b26880183bbfbff25f697a0c5a95b7fb6`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.package.inspect`

Read installed-package identity and version metadata without mutation.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux package inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `7f030f057abfc1b5660cb37fc074009d4b3e0af2ee7c2476bc8c1754241fa153`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.package.verify`

Run a native read-only integrity check for one installed package.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux package verify {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `9a0057221b2cf37455327ac153b33c6ebd215d53efa58d3682e087fc20688b48`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.process.inspect`

Inspect one process tree anchor and its bounded execution context.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux process inspect {pid}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `62b65eefe6fda8334afa000a9c43752aa7718122b12f85c1ef31f40fb825513c`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "pid": {
      "type": "integer",
      "minimum": 1
    }
  },
  "required": [
    "pid"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.process.list`

List bounded and redacted process metadata from the local host.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux process list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `f170a7e39e28ee35d824b9b0d19bb85ffb2dc140012599f3db3d9152d8f43db6`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.process.logs`

Query bounded logs for one policy-classified stable process resource identity.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `9d6ecc1da31f274d618b580cf756923685f41b6928df5379e15cfceaf98fec1a`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "since": {
      "type": "string"
    },
    "until": {
      "type": "string"
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100000000
    }
  },
  "required": [
    "resource_id",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "bytes": {
      "type": "integer",
      "minimum": 0
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    }
  },
  "required": [
    "status",
    "artifact_ref",
    "bytes",
    "observed_at",
    "truncated"
  ],
  "additionalProperties": false
}
```

## `linux.process.resources`

Read bounded resource counters for one explicit process identifier.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux process resources {pid}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `799d091ca798b989ccc24794169fefd3b661d726e3d8368e18897c9e940a16ac`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "pid": {
      "type": "integer",
      "minimum": 1
    }
  },
  "required": [
    "pid"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.process.restart`

Request bounded restart of one discovered process resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `4e5b742d88c27a1a5344b082769c4fd249703f5b448eab199f293940d5d91561`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 120
    }
  },
  "required": [
    "resource_id",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.process.signal`

Send one bounded non-KILL signal to a discovered process resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `942672419771cd720c99ee51f0718d3f7d45a520dd43f08dc02f904651eb4abb`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "signal": {
      "type": "string",
      "enum": [
        "HUP",
        "TERM",
        "USR1",
        "USR2"
      ]
    }
  },
  "required": [
    "resource_id",
    "signal"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.process.start`

Request startup of one discovered process resource through a gated adapter binding.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `854ac78276ac64c5c8ba9be45725161b8bff9460302901f14813f04959f3d1d1`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "args": {
      "type": "array",
      "items": {
        "type": "string"
      },
      "maxItems": 32
    }
  },
  "required": [
    "resource_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.process.stop`

Request bounded termination of one discovered process resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `64e2b24d823572c17de43d5af32e8e65b847862af476222bcde465d0fbce7c38`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 120
    }
  },
  "required": [
    "resource_id",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.resource.cpu`

Read bounded CPU topology, architecture, and load metadata.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux resource cpu`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `be8786ee0fd41a7aa37383027fa071fdd83287815a60790a9428d72351193f26`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.resource.disk`

Read filesystem capacity for one explicit existing path.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux resource disk`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `fe28f84d92f69da92d7992a4234543c6d45a9452e900373378789fba68d9f502`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.resource.gpu`

Read available GPU identity, driver, memory, thermal, and utilization metadata.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux resource gpu`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `1bc66d597892890e4cf517dba0d3def5ced3afdd076bc17b591291acb475453f`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.resource.memory`

Read physical memory totals and current availability when supported.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux resource memory`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `2f0f241a30af3091419dee43a1f59fba22fe78fedd6c93742f98f8743a8df1f3`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.resource.snapshot`

Read one bounded CPU, memory, and filesystem resource snapshot.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux resource snapshot`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `2fd77a98621c8940330fb4d282db16fe905055248a471509315ad7fccbc75423`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    }
  },
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.schedule.disable`

Request persistent disablement of one discovered schedule resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `d6c6073956b5717305b56ae58362998fb2bc60f1a1f2adab4a248d529788c750`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "resource_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.schedule.enable`

Request persistent enablement of one discovered schedule resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `71dbf0d047cee0387d80084fdfd11b8167f91fa9942712adb3c60318035ef8cd`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "resource_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.schedule.inspect`

Inspect one system timer or scheduled task without running it.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux schedule inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `0628481b0dadde2afba4b40b18363e84b5a98428a36cbcf4ee04755f600d800f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.schedule.list`

List bounded system timer, cron, or scheduled task metadata.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux schedule list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `f246a5e208f6c932f35a70f8861266494a22d9c74d23251987ed35ea14ae87b9`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.schedule.run`

Request one immediate run of a discovered schedule resource without changing its cadence.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `5c9db1b7b741e726624b0194dc0e7bbb7ce4182f6b5780e5425c3735de4f33a0`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 120
    }
  },
  "required": [
    "resource_id",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.service.disable`

Request persistent disablement of one discovered operating-system service resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `d901534ec3afa5469eff0df0c58d6c18da334954561886b04dd6d3601051d921`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "resource_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.service.enable`

Request persistent enablement of one discovered operating-system service resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `744f891ac1a998ed3df9093dd016ef7bee162311393a377919ff0e649d61adcb`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "resource_id"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.service.inspect`

Inspect one service definition, state, dependencies, and launch context.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux service inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `8f7e220306b3887aaf815570ba3581c6f2a924ceb899fd5753b303132364509f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.service.list`

List bounded service metadata through the native service manager.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux service list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `779b06af95ae477dcab3c05801ebb8cf9ee2a821065a40ae72899988b05b676b`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.service.logs`

Query bounded logs for one policy-classified stable service resource identity.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `38ec1acfab743a12df0400bb277b01d8d4f7b3625aa78794ce0e2655028f5150`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "since": {
      "type": "string"
    },
    "until": {
      "type": "string"
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100000000
    }
  },
  "required": [
    "resource_id",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "bytes": {
      "type": "integer",
      "minimum": 0
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    }
  },
  "required": [
    "status",
    "artifact_ref",
    "bytes",
    "observed_at",
    "truncated"
  ],
  "additionalProperties": false
}
```

## `linux.service.restart`

Request bounded restart of one discovered operating-system service resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `fb268ba8da22f13b2df0bbae348b396ccee16c0af6a8f1e3de486287c2b0cb77`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 120
    }
  },
  "required": [
    "resource_id",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.service.start`

Request startup of one discovered operating-system service resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `caa7061ada0df217ece1090d33c8116d83ed725193e709a01c4ceb46017fa7b5`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 120
    }
  },
  "required": [
    "resource_id",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.service.stop`

Request bounded stop of one discovered operating-system service resource.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `ba85102f1184891115a42442193f067ee2ff2d6278b26ea22e4849bdc217f175`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "resource_id": {
      "type": "string",
      "minLength": 1
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 120
    }
  },
  "required": [
    "resource_id",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `linux.time.status`

Read wall-clock, timezone, and monotonic-clock metadata without synchronization.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `linux` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux time status`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `9688e8586a617e3cc4630ac87d7bb20e5806033ecac0a4ff409782de5dd34b09`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `linux.time.synchronize`

Request one bounded host clock synchronization through an available time service.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `linux` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `4144fe96e14109e3ef710e6bd8992eb2ea10fddcc31b82ffec3a418efe1e2227`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "source": {
      "type": "string",
      "enum": [
        "system",
        "ntp",
        "ptp",
        "chrony"
      ]
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 120
    }
  },
  "required": [
    "source",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "target": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "target",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `middleware.graph.snapshot`

Read a bounded process and interface relationship snapshot for local middleware.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `middleware` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl middleware graph snapshot`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `4ccaf404c971b8fb9066cbf1cfe65e6c4f39277574041f9095d7b44ecb4575cb`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string",
      "enum": [
        "middleware.graph.snapshot"
      ]
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `middleware.inspect`

Identify available middleware control planes from bounded host evidence.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `middleware` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl middleware inspect`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `4acd116d92242c36badfcb47351a8b729b335c1c11ce3ece66934ee4c7a27439`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string",
      "enum": [
        "middleware.inspect"
      ]
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `middleware.status`

Read a compact status summary of locally discovered middleware interfaces.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `middleware` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `10s`
- Canonical CLI template: `robotctl middleware status`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `e6d96ec293e77cefa6592b00bea8469d608a9bfd9b808e5daef31182bed8adb4`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string",
      "enum": [
        "middleware.status"
      ]
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.action.describe`

Read client, server, and type metadata for one observed ROS 2 action.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros action describe {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `a103b3947e75f4bf79a20e453b6532213c9648c763c54d3004d1038afebffaf9`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.action.list`

List bounded ROS 2 action names and declared types.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros action list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `0a5b0760cafd3595359729bf98c3f7d73902a18a3901ca3ef38a501b81d6b68c`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.action.status`

Read bounded goal-status observations for one explicit ROS action endpoint.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `0af4e2835e25dacb70743976c0ad6f8fdf10853ec84d7ffb69d5416d4fa286ac`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    },
    "goal_id": {
      "type": "string"
    },
    "limit": {
      "type": "integer",
      "minimum": 1,
      "maximum": 100
    }
  },
  "required": [
    "name",
    "limit"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "action": {
      "type": "string"
    },
    "goals": {
      "type": "array",
      "maxItems": 100,
      "items": {
        "type": "object",
        "properties": {
          "goal_id": {
            "type": "string"
          },
          "state": {
            "type": "string"
          },
          "observed_at": {
            "type": "string"
          }
        },
        "required": [
          "goal_id",
          "state",
          "observed_at"
        ],
        "additionalProperties": false
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "action",
    "goals",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `ros.bag.inspect`

Read bounded metadata for one explicit ROS 2 or ROS 1 bag path.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros bag inspect {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `d312aaf354cfe8d76a6311533f6797852c6b2fdbb04bdaa7ef8e8925b59319d4`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "path": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "path"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.clock.status`

Inspect ROS clock-topic availability without sampling or changing time.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros clock status`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `0a7ef2afb29732ba95356c46b2518c3186eaea3c9832b53393cc7f9cbdc7372f`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.diagnostics.snapshot`

Collect a bounded category-filtered diagnostic snapshot from the observable ROS graph.

- Lifecycle/version: `GATEABLE` / `2.0.0`
- Layer/access/risk: `ros` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `BOUNDED_STREAM`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `144d9c5724a67f1b00c858eeaebf2a625788b94b2a0cb84ea8430c7173c5a65f`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "category": {
      "type": "string",
      "enum": [
        "all",
        "hardware",
        "software"
      ]
    },
    "duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 30
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 1000000
    }
  },
  "required": [
    "category",
    "duration_s",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "status",
    "observed_at",
    "truncated",
    "items"
  ],
  "additionalProperties": false
}
```

## `ros.diagnostics.watch`

Watch diagnostic messages within explicit time, item, and byte limits.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `BOUNDED_STREAM`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `639a1b2ed3bdb30eaac19b097d99ee249b5177618051e80dc848a7dc218c1ecd`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 30
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 1000000
    }
  },
  "required": [
    "duration_s",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "status",
    "observed_at",
    "truncated",
    "items"
  ],
  "additionalProperties": false
}
```

## `ros.graph.snapshot`

Capture a bounded read-only snapshot of the currently observable ROS graph.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros graph snapshot`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `ac73b823658cdad95610a27614ca9069c8f30256586960b57e3c8a7afe47610e`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "layer": {
      "type": "string",
      "enum": [
        "ros"
      ]
    },
    "status": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "errors": {
      "type": "array",
      "items": {
        "type": "string"
      }
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "layer",
    "status",
    "data",
    "warnings",
    "errors",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `ros.node.activate`

Request activation of one ROS 2 managed-lifecycle node.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_TRANSITION, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `016fa9dadf8aaab6ed8e3b8b406ff8fbe68d1d8dea1e6041427fca9feb684d6d`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "node": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "node",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `ros.node.deactivate`

Request deactivation of one ROS 2 managed-lifecycle node.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `write` / `R2`
- Data classification: `INTERNAL`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_TRANSITION, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `9854d3d8eabe0c5ce5458cb74a3449cc52fb54b73ba346362cae6e2bec30e491`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "node": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "node",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `ros.node.inspect`

Inspect one observed ROS node and its declared interfaces.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros node inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `7a3d5df53b9c79d92b92bf53c86dd7859e609d2e983f74c01f515e72acba5eb5`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.node.lifecycle`

Read one ROS 2 managed node lifecycle state when available.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros node lifecycle {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `251123aa597d0156cee27e1e67b8ea086c618857d390b693cd7c694ade7cebe6`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.node.list`

List bounded node names from the observable ROS graph.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros node list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `0ba9f5545d67b912a3f9e7964d777dd8b18f1be807f69eda51f62588804dcae2`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.node.status`

Read compact visibility status for one ROS node without interface inspection.

- Lifecycle/version: `RELEASED` / `2.0.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros node status {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `a0e964e1fa955d618bd858c894482f930f82f2a6f2c1462210582e67f012a58e`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string",
      "enum": [
        "ros.node.status"
      ]
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {
        "name": {
          "type": "string"
        },
        "visible": {
          "type": "boolean"
        },
        "ros_version": {
          "type": "integer",
          "minimum": 1,
          "maximum": 2
        }
      },
      "required": [
        "name",
        "visible"
      ],
      "additionalProperties": false
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.parameter.describe`

Read one ROS 2 parameter descriptor without changing its value.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros parameter describe {name} --node {node}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `66c4295a9c279bd0676a97abef2ffb6af39f750e899dbe077db1e15419f357d8`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "node": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "node",
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.parameter.dump`

Export bounded parameter values for one explicit ROS node to an artifact reference.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `9d867719dc2e7490f43f59c6bb6110234ae96293aabb3fc7501100f4802c04a4`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "node": {
      "type": "string",
      "minLength": 1
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 10000000
    }
  },
  "required": [
    "node",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "node": {
      "type": "string"
    },
    "artifact_ref": {
      "type": "string"
    },
    "media_type": {
      "type": "string",
      "enum": [
        "application/yaml"
      ]
    },
    "bytes": {
      "type": "integer",
      "minimum": 0
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "node",
    "artifact_ref",
    "media_type",
    "bytes",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `ros.parameter.get`

Read one parameter value from an explicit ROS node namespace.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros parameter get {name} --node {node}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `aa03ac032dbb357d4630aaa6a532ff27f18a1e701445bef704c35ba7a7df9ab8`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "node": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "node",
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.parameter.list`

List bounded parameter names visible through the active ROS graph.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros parameter list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `77ccc4c8687e0306341d3f424c1df0f2516dbdce4a37e9d76d40d5c0a0cff12a`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.parameter.load`

Request bounded ROS parameter loading from a digest-pinned protected artifact.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `true`
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_INPUT, PRECONDITION_FAILED, CONFLICT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `9c92d4dfd4cdaf95445dbfab0b6be171ea9974490f9ee5bca8a58e5842f25d28`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "node": {
      "type": "string",
      "minLength": 1
    },
    "artifact_ref": {
      "type": "string",
      "minLength": 12
    },
    "artifact_sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64
    },
    "format": {
      "type": "string",
      "enum": [
        "ros1_yaml",
        "ros2_yaml"
      ]
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1,
      "maximum": 10000000
    },
    "expected_parameter_state_sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64
    }
  },
  "required": [
    "node",
    "artifact_ref",
    "artifact_sha256",
    "format",
    "max_bytes",
    "expected_parameter_state_sha256"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "node": {
      "type": "string"
    },
    "change_set_id": {
      "type": "string"
    },
    "rollback_token": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "node",
    "change_set_id",
    "rollback_token",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `ros.parameter.rollback`

Request rollback of one ROS parameter change set under a new quiescence lease.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `true`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_INPUT, PRECONDITION_FAILED, CONFLICT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `43bb9088f8c41b2348869a7d66f0ec0bfd49923191d057963fc2294da01ffadd`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "node": {
      "type": "string",
      "minLength": 1
    },
    "rollback_token": {
      "type": "string",
      "minLength": 12
    },
    "expected_parameter_state_sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64
    }
  },
  "required": [
    "node",
    "rollback_token",
    "expected_parameter_state_sha256"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "node": {
      "type": "string"
    },
    "change_set_id": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "node",
    "change_set_id",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `ros.parameter.set`

Request one typed ROS parameter update under an execution-quiescence lease.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `write` / `R2`
- Data classification: `SENSITIVE`
- Result semantics: `ACKNOWLEDGEMENT_ONLY`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `false` / `false`
- Requires execution quiescence: `true`
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_INPUT, PRECONDITION_FAILED, CONFLICT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `8a057246237d6aa173daa8708d209cdf5e1fa2fa5d22337839fdd70fa52ba300`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "node": {
      "type": "string",
      "minLength": 1
    },
    "name": {
      "type": "string",
      "minLength": 1
    },
    "value": {
      "type": "object",
      "properties": {
        "type": {
          "type": "string",
          "enum": [
            "boolean",
            "integer",
            "number",
            "string",
            "array",
            "object",
            "null"
          ]
        },
        "value_json": {
          "type": "string",
          "maxLength": 1000000
        }
      },
      "required": [
        "type",
        "value_json"
      ],
      "additionalProperties": false
    },
    "expected_current_sha256": {
      "type": "string",
      "minLength": 64,
      "maxLength": 64
    }
  },
  "required": [
    "node",
    "name",
    "value",
    "expected_current_sha256"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "node": {
      "type": "string"
    },
    "name": {
      "type": "string"
    },
    "rollback_token": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "node",
    "name",
    "rollback_token",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `ros.service.describe`

Read declared type metadata for one observed ROS service.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros service describe {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `ac0b23b6788a0069fc79f0e2418ed3b71bf21323dff5febfe3a8e5afcfcb89ca`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.service.list`

List bounded ROS service names and declared types.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros service list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `ec1f2adc21765f60e9c79d50d3bad9f5cd54eabc079c5dc8a4cefe191a582f70`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.tf.lookup`

Read one bounded transform between explicit source and target ROS frames.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `2f70467c7ba9e850f14712066660babcc5866dd2a5d98d2463f4f3328078973a`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "source_frame": {
      "type": "string",
      "minLength": 1
    },
    "target_frame": {
      "type": "string",
      "minLength": 1
    },
    "timeout_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 10
    }
  },
  "required": [
    "source_frame",
    "target_frame",
    "timeout_s"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "source_frame": {
      "type": "string"
    },
    "target_frame": {
      "type": "string"
    },
    "translation_m": {
      "type": "object",
      "properties": {
        "x": {
          "type": "number"
        },
        "y": {
          "type": "number"
        },
        "z": {
          "type": "number"
        }
      },
      "required": [
        "x",
        "y",
        "z"
      ],
      "additionalProperties": false
    },
    "rotation_xyzw": {
      "type": "object",
      "properties": {
        "x": {
          "type": "number"
        },
        "y": {
          "type": "number"
        },
        "z": {
          "type": "number"
        },
        "w": {
          "type": "number"
        }
      },
      "required": [
        "x",
        "y",
        "z",
        "w"
      ],
      "additionalProperties": false
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "source_frame",
    "target_frame",
    "translation_m",
    "rotation_xyzw",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `ros.tf.monitor`

Monitor ROS transforms within explicit time, item, and byte limits.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `BOUNDED_STREAM`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `a49d454fe19ee07e95f543cfda003b824c02645f22a8087a40a9cc957a337985`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "source_frame": {
      "type": "string"
    },
    "target_frame": {
      "type": "string"
    },
    "duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 30
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 1000000
    }
  },
  "required": [
    "duration_s",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "status",
    "observed_at",
    "truncated",
    "items"
  ],
  "additionalProperties": false
}
```

## `ros.tf.snapshot`

Read a bounded instantaneous transform snapshot with explicit frame identities.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `6654249a659053acc718065d0ca578e063e39c23713e8507e43075067a27faac`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 2000
    }
  },
  "required": [
    "max_items"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "transforms": {
      "type": "array",
      "maxItems": 2000,
      "items": {
        "type": "object",
        "properties": {
          "parent": {
            "type": "string"
          },
          "child": {
            "type": "string"
          },
          "translation_m": {
            "type": "object",
            "properties": {
              "x": {
                "type": "number"
              },
              "y": {
                "type": "number"
              },
              "z": {
                "type": "number"
              }
            },
            "required": [
              "x",
              "y",
              "z"
            ],
            "additionalProperties": false
          },
          "rotation_xyzw": {
            "type": "object",
            "properties": {
              "x": {
                "type": "number"
              },
              "y": {
                "type": "number"
              },
              "z": {
                "type": "number"
              },
              "w": {
                "type": "number"
              }
            },
            "required": [
              "x",
              "y",
              "z",
              "w"
            ],
            "additionalProperties": false
          },
          "observed_at": {
            "type": "string"
          }
        },
        "required": [
          "parent",
          "child",
          "translation_m",
          "rotation_xyzw",
          "observed_at"
        ],
        "additionalProperties": false
      }
    },
    "truncated": {
      "type": "boolean"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "transforms",
    "truncated",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `ros.tf.tree`

Read a bounded parent-child frame tree from the observable ROS transform graph.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `833dcd738f54c10c2aa153c61f7f69c8b5bd4dbeef5b8f623f5ac439be8526fc`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 2000
    }
  },
  "required": [
    "max_items"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "frames": {
      "type": "array",
      "maxItems": 2000,
      "items": {
        "type": "string"
      }
    },
    "edges": {
      "type": "array",
      "maxItems": 2000,
      "items": {
        "type": "object",
        "properties": {
          "parent": {
            "type": "string"
          },
          "child": {
            "type": "string"
          }
        },
        "required": [
          "parent",
          "child"
        ],
        "additionalProperties": false
      }
    },
    "truncated": {
      "type": "boolean"
    },
    "observed_at": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "frames",
    "edges",
    "truncated",
    "observed_at"
  ],
  "additionalProperties": false
}
```

## `ros.topic.bandwidth`

Measure bounded topic bandwidth intervals without retaining message payloads.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R1`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `BOUNDED_STREAM`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `7347e00c188e8b3a4c6941494eee6dd61339071c73171cc1d44e6c31dc852338`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    },
    "duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 30
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 1000000
    }
  },
  "required": [
    "name",
    "duration_s",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "status",
    "observed_at",
    "truncated",
    "items"
  ],
  "additionalProperties": false
}
```

## `ros.topic.describe`

Read publisher, subscriber, and type metadata for one observed topic.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros topic describe {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `b7a1f69371c5ab9884f9b47928277b49c7bce6cc28f528bd9159ea48d33a9f32`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "name"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.topic.list`

List bounded topic names and declared types from the observable ROS graph.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros topic list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `bdc3122355a2afd0494871dd39461c95087237e3f56428736be6548e35c05e24`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "operation": {
      "type": "string"
    },
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "data": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "evidence": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "warnings": {
      "type": "array",
      "items": {
        "type": "string"
      }
    }
  },
  "required": [
    "schema_version",
    "operation",
    "status",
    "observed_at",
    "data",
    "evidence",
    "warnings"
  ],
  "additionalProperties": false
}
```

## `ros.topic.rate`

Measure bounded topic publication-rate intervals without returning payload values.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R1`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `BOUNDED_STREAM`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `2b1b373afaea5a9ccdf69a7b58a6acb403be5a04b296d0825ab50f87ae158f10`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    },
    "duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 30
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 1000000
    }
  },
  "required": [
    "name",
    "duration_s",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "status",
    "observed_at",
    "truncated",
    "items"
  ],
  "additionalProperties": false
}
```

## `ros.topic.sample`

Collect a bounded set of structured samples from one explicit ROS topic.

- Lifecycle/version: `GATEABLE` / `1.1.0`
- Layer/access/risk: `ros` / `read` / `R1`
- Data classification: `SENSITIVE`
- Result semantics: `OBSERVATION`
- Observation overhead: `ELEVATED`
- Execution mode: `BOUNDED_STREAM`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `true`
- Requires execution quiescence: `false`
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `efba3bfee2a8cd6683e2602e2f43aa80c24886a404bd8568cdca140222e506ce`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "name": {
      "type": "string",
      "minLength": 1
    },
    "duration_s": {
      "type": "number",
      "minimum": 0.1,
      "maximum": 30
    },
    "max_items": {
      "type": "integer",
      "minimum": 1,
      "maximum": 1000
    },
    "max_bytes": {
      "type": "integer",
      "minimum": 1024,
      "maximum": 1000000
    }
  },
  "required": [
    "name",
    "duration_s",
    "max_items",
    "max_bytes"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "observed_at": {
      "type": "string"
    },
    "truncated": {
      "type": "boolean"
    },
    "items": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "status",
    "observed_at",
    "truncated",
    "items"
  ],
  "additionalProperties": false
}
```

## `runtime.health`

Read local Rolo runtime readiness, version, and registered robot count.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `control` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `5s`
- Canonical CLI template: `robotctl runtime health`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `a0c6413ec9c6e1c817897265ab65cf7b0eefbe3ee36e33802615e4aac328387f`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "version": {
      "type": "string"
    },
    "registered_robots": {
      "type": "integer",
      "minimum": 0
    },
    "artifact_root": {
      "type": "string"
    },
    "error": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "version"
  ],
  "additionalProperties": false
}
```

## `runtime.version`

Read installed Rolo and supported contract protocol versions.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `control` / `read` / `R0`
- Data classification: `PUBLIC`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `5s`
- Canonical CLI template: `robotctl runtime version`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `4debde3f3043ae71d2609d2b1b31bf5bd71e62f367a43c1afb1b3e1b15dce624`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "status": {
      "type": "string"
    },
    "version": {
      "type": "string"
    },
    "operation_contract_schema": {
      "type": "string"
    },
    "adapter_protocol": {
      "type": "string"
    },
    "tool_catalog_schema": {
      "type": "string"
    }
  },
  "required": [
    "status",
    "version",
    "operation_contract_schema",
    "adapter_protocol",
    "tool_catalog_schema"
  ],
  "additionalProperties": false
}
```

## `state.graph.query`

Search active State Graph nodes and edges with one bounded text term.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `control` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `5s`
- Canonical CLI template: `robotctl state graph query {query} --robot {robot_id}`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `ed5da2053b763126ef4366e91c57749ade2b05af71ed9a2ca14a54f0ea30dae1`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "query": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "query"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "robot_id": {
      "type": "string"
    },
    "discovery_id": {
      "type": "string"
    },
    "query": {
      "type": "string"
    },
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "truncated": {
      "type": "boolean"
    }
  },
  "required": [
    "schema_version",
    "robot_id",
    "discovery_id",
    "query",
    "nodes",
    "edges",
    "truncated"
  ],
  "additionalProperties": false
}
```

## `state.graph.snapshot`

Read the State Graph from one robot's active gated adapter release.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `control` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `5s`
- Canonical CLI template: `robotctl state graph snapshot --robot {robot_id}`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `b797a0713ce068e6e9cd8a51615c85b4a50cc8a050b50f6c1d56371f699e2a44`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "robot_id": {
      "type": "string"
    },
    "discovery_id": {
      "type": "string"
    },
    "nodes": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    },
    "edges": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "schema_version",
    "robot_id",
    "discovery_id",
    "nodes",
    "edges"
  ],
  "additionalProperties": false
}
```

## `tool.catalog`

Read the active gated Tool Catalog for one robot identity.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `control` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `5s`
- Canonical CLI template: `robotctl tool catalog --robot {robot_id}`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `c1a599f007eec664ef961a173aa6e9b5d88770b93b3f5c2029418cdef2c7a3f0`

Input schema:

```json
{
  "type": "object",
  "properties": {},
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "schema_version": {
      "type": "string"
    },
    "robot_id": {
      "type": "string"
    },
    "discovery_id": {
      "type": "string"
    },
    "contract_catalog_sha256": {
      "type": "string"
    },
    "tools": {
      "type": "array",
      "items": {
        "type": "object",
        "properties": {},
        "additionalProperties": true
      }
    }
  },
  "required": [
    "schema_version",
    "robot_id",
    "discovery_id",
    "contract_catalog_sha256",
    "tools"
  ],
  "additionalProperties": false
}
```

## `tool.schema`

Read the active input and output contract for one canonical operation.

- Lifecycle/version: `RELEASED` / `1.1.0`
- Layer/access/risk: `control` / `read` / `R0`
- Data classification: `INTERNAL`
- Result semantics: `OBSERVATION`
- Observation overhead: `BOUNDED`
- Execution mode: `REQUEST_RESPONSE`
- Paired operation: `none`
- Replacement operation: `none`
- Idempotent/cancelable: `true` / `false`
- Requires execution quiescence: `false`
- Maximum duration: `5s`
- Canonical CLI template: `robotctl tool schema {operation} --robot {robot_id}`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `737435d57292f7665dcf78a7693c435af9c5d5fd90e91018b5d025a8fa478beb`

Input schema:

```json
{
  "type": "object",
  "properties": {
    "operation": {
      "type": "string",
      "minLength": 1
    }
  },
  "required": [
    "operation"
  ],
  "additionalProperties": false
}
```

Output schema:

```json
{
  "type": "object",
  "properties": {
    "operation": {
      "type": "string"
    },
    "input_schema": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "output_schema": {
      "type": "object",
      "properties": {},
      "additionalProperties": true
    },
    "availability": {
      "type": "string"
    }
  },
  "required": [
    "operation",
    "input_schema",
    "output_schema",
    "availability"
  ],
  "additionalProperties": false
}
```
