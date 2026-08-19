# Authored Operation Contracts

This document is generated from `src/rolo/operation_contracts/*.yaml`. 
`RELEASED` contracts back built-in operations; `GATEABLE` contracts may be 
implemented and promoted by Adapt. The remaining product vocabulary stays `DRAFT` 
and cannot become `VERIFIED` until an authored contract is added.

Catalog SHA-256: `b4d7c4da64913247f79ed6e10b8938c2c3c415cae33a8064565dfe996b3ab1e7`

| Operation | Lifecycle | Version | Data | Contract SHA-256 |
|---|---|---|---|---|
| `app.base.status` | GATEABLE | `1.1.0` | `INTERNAL` | `2360007d6f4f4d6747ba2486fb72391e8d4943ada52b9a59f17185ec1fc1ef6c` |
| `app.calibration.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `9e21576b94327507ac318e15c0e773a7dc0bf691fbed95c325cc8fac44aeae87` |
| `app.calibration.list` | GATEABLE | `1.1.0` | `INTERNAL` | `2ac48c3ca6d61ad2843eaa46ed335fc36ef7c8059d34b0a9dfa99b8a25a707a1` |
| `app.calibration.status` | GATEABLE | `1.1.0` | `INTERNAL` | `1648e823c39812a9fe2d525af5949f944f7b85053b5f60b053551b97f4c6793a` |
| `app.calibration.validate` | GATEABLE | `1.1.0` | `SENSITIVE` | `aae319a905c3bca555ae967d5196b9911cf8a619b9adc2feb4386fb0b5bd0ec8` |
| `app.camera.calibration.status` | GATEABLE | `1.1.0` | `INTERNAL` | `4bfd1e0049bbcaf8e38b327ad10474d1de4ca0338deec53838e72a4285da487c` |
| `app.camera.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `07b446ad7f7592b53907073d24e9d0d814d69963bd1439ea05461beff65c5849` |
| `app.camera.list` | GATEABLE | `1.1.0` | `INTERNAL` | `c96ae66314c186f7612289542d38054bdb4dcac73bf06c2e3c54b6f9c867dcde` |
| `app.camera.snapshot` | GATEABLE | `1.1.0` | `SENSITIVE` | `0755ebedfca8b5a8cb198961b83222e9c3b93a323c4596496cbbb84de33e65f0` |
| `app.camera.status` | GATEABLE | `1.1.0` | `INTERNAL` | `fc662b5d33465eb5b12e3a8559231fd7f0edaf1c8466d9dc6b41e472971d1cb4` |
| `app.camera.stream.start` | GATEABLE | `1.1.0` | `SENSITIVE` | `89b4c805b768426b8954f240bb188d81c53a1410c068687140902fe7d55a4c83` |
| `app.camera.stream.stop` | GATEABLE | `1.1.0` | `SENSITIVE` | `801df85008c188e05820c2b7e310b48a901fe4f7528486588341f48d7597c421` |
| `app.diagnosis.cancel` | GATEABLE | `1.1.0` | `SENSITIVE` | `a61ff29823e8dfc945ce5034ea0f01eba591a18930df6ca6044292519668d589` |
| `app.diagnosis.evidence` | GATEABLE | `1.1.0` | `SENSITIVE` | `c0ffaad9ea7fb3748dc4c1baa7ac3ea04c4ac0b315db4e2d5073304d82935f3d` |
| `app.diagnosis.result` | GATEABLE | `1.1.0` | `SENSITIVE` | `2745aeff8db907c721063d78fda952e936985ca75f6c4e286408bbc6c53e9ce3` |
| `app.diagnosis.run` | GATEABLE | `1.1.0` | `SENSITIVE` | `34c6c3e2f3913b5e5a9cd5ad484023d8ddb77bb8ae69ea9768f573d130bc3550` |
| `app.diagnosis.snapshot` | GATEABLE | `1.1.0` | `SENSITIVE` | `bcd742d2936be84e3557928d6874cf0d55fb7feb680e4174c24d1127284aa1f2` |
| `app.diagnosis.status` | GATEABLE | `1.1.0` | `INTERNAL` | `6719c7f1dbd1908293d49dcf0b64d2607bc63d944cc04ca80d39605101c90ed0` |
| `app.event.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `2e3373c872fc153dd12fbb988cf9457d6fc23d1961f532c80b08a21c32935331` |
| `app.event.list` | GATEABLE | `1.1.0` | `SENSITIVE` | `dc3ece5497392b493d3bb6ed3b353e4ed230b9c596f11f83c501b8f2801aa981` |
| `app.gnss.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `67cec17a19623912fb56846198b664151c779e96d1c8cf2dc58b25dd46593472` |
| `app.gnss.list` | GATEABLE | `1.1.0` | `INTERNAL` | `ce6d31ed0cdb83e61aa0afed28cf0815a95b1a5aa9e87fbb728212c2f554e06a` |
| `app.gnss.sample` | GATEABLE | `1.1.0` | `SENSITIVE` | `363bd8d76009821ef77b7faace3a4456270f90ab5067ee1781607fbbd0c51965` |
| `app.gnss.status` | GATEABLE | `1.1.0` | `INTERNAL` | `4b050fa8d74d57359568f3a729e074b579031f5e4711f57fa8a5730795e6f99a` |
| `app.gripper.status` | GATEABLE | `1.1.0` | `INTERNAL` | `26b84de8909b800322caf20d1a0fc79913aa00aacba8f9fc1f5a6948d05fb549` |
| `app.imu.calibration.status` | GATEABLE | `1.1.0` | `INTERNAL` | `8c12bd3de93d4aed705f197bb3016a6c5f26afe8ace15d5fe71935124928d832` |
| `app.imu.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `ea0472c4c16333f64a46484114e395753d9690cb30f85ecd6cdd31c40921e9fa` |
| `app.imu.list` | GATEABLE | `1.1.0` | `INTERNAL` | `711ba8512b3095c6251abdabfec2dcf4c67eb98d9144c184893155ad9294a9ad` |
| `app.imu.sample` | GATEABLE | `1.1.0` | `SENSITIVE` | `fe0ee487bfcecf86f98e80617b751689e05b308f8823002a632babec18066477` |
| `app.imu.status` | GATEABLE | `1.1.0` | `INTERNAL` | `e99054394d8ceb219c88fa830fabffa3f07f46e7b5bdeb60d01e7465e518bd3a` |
| `app.lidar.calibration.status` | GATEABLE | `1.1.0` | `INTERNAL` | `a0ae11e7c079174f23f71eef1190eaa341fc691fcb429cdfeb56a2ae36d05677` |
| `app.lidar.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `d73b9ce5680ab0ae8d1538d6d44185ea63ecc9f70ea6bbf8d3a5afb5b149ec16` |
| `app.lidar.list` | GATEABLE | `1.1.0` | `INTERNAL` | `e94c564050cf03cb714f97e7870373275acf40082279ca27b36707e39c336926` |
| `app.lidar.snapshot` | GATEABLE | `1.1.0` | `SENSITIVE` | `cfa165225acf315dfec9b436eea858338eb59444bfa7b9ac60e4faec27df1d51` |
| `app.lidar.status` | GATEABLE | `1.1.0` | `INTERNAL` | `9d1ec2cc089e762ac2a2b8f2fc2a39719b0fd7c297e1120bf39be73a23473f4c` |
| `app.localization.initialize` | GATEABLE | `1.1.0` | `SENSITIVE` | `bab27878079b6199173d0527c5930b3331236ef410e200a0acb0299394f81a5e` |
| `app.localization.pose` | GATEABLE | `1.1.0` | `SENSITIVE` | `3a7ae4c05a97e2b3485b7c8b185cb34a963ee6973fcd8d407254b9d6c35e83fc` |
| `app.localization.quality` | GATEABLE | `1.1.0` | `INTERNAL` | `29bcec8471902356a17c7673ff5c18b84933a4b16972967f6dc6663a6d2339da` |
| `app.localization.relocalize` | GATEABLE | `1.1.0` | `SENSITIVE` | `b330371e02385a9d13cac6641b9a140dc71aa14c0a8a0b14ab69edc8d8c98a69` |
| `app.localization.reset` | GATEABLE | `1.1.0` | `INTERNAL` | `d87d8d81e7b4ffc35cc275d5bc9c62df2d9d9dfe5e836efb876848f8d0500387` |
| `app.localization.status` | GATEABLE | `1.1.0` | `INTERNAL` | `ca4b98b12b9b99f09c38e4cdc2d79f7d1ac3f682bb0d5fde8b0508e2cc90d99f` |
| `app.manipulation.plan` | GATEABLE | `1.1.0` | `SENSITIVE` | `b810b4393ca7e5f5c9f3e537275543f534350def904496fb91011270d3028415` |
| `app.manipulation.status` | GATEABLE | `1.1.0` | `INTERNAL` | `d34b3e97c307437ad8772d3bf13e9f5172085c2864b7c5d03f58111a79f4ce70` |
| `app.map.clear` | GATEABLE | `1.1.0` | `SENSITIVE` | `dfee965210d933094c96c8063dfca5d802ec7e6aa805607277687a029e8379f4` |
| `app.map.create` | GATEABLE | `1.1.0` | `SENSITIVE` | `e648f8d93c3d76a5ccc7de22b293c5bd4cdebd4bd635e0c23bbe9256d73e531d` |
| `app.map.export` | GATEABLE | `1.1.0` | `SENSITIVE` | `034a07416e6e4715fada56e2907323d4d536257ef41a84f0fa4c72f7dfd13e45` |
| `app.map.import` | GATEABLE | `1.1.0` | `SENSITIVE` | `a974ab5b92675c6d1d47a21b414429296717402334fc1c667c89511988250d0f` |
| `app.map.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `346c9343b63398a24891f840bbe9b3ceb8c8dac6a70a9573697ec41ee3628fc9` |
| `app.map.list` | GATEABLE | `1.1.0` | `SENSITIVE` | `347f1bf4362908ca33e62b40a27220671a51696cc4b5be1139b5529249f7fed1` |
| `app.map.load` | GATEABLE | `1.1.0` | `SENSITIVE` | `f6f54bd9d9e510df928ef79168258b0d8f4e7fcee011127fea9d85ba83e08111` |
| `app.map.save` | GATEABLE | `1.1.0` | `SENSITIVE` | `e5466ee2fc52571fe11d36f7ee085e0484a6807b9ef11f2888b78ce8a03f3878` |
| `app.navigation.costmap.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `e6997ffa709c5ec331919d087926079d40f5ac8c68089f808276c1af489516d3` |
| `app.navigation.path.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `2ef63291d2ff86a1b98996fe2c05f9105595573043daa3ebe7b7fbf9108f13a4` |
| `app.navigation.plan` | GATEABLE | `1.1.0` | `SENSITIVE` | `b98a5d0b9e88a5897c647a23956c426ea599077174f2bd4fc9bd13604f9f4c99` |
| `app.navigation.status` | GATEABLE | `1.1.0` | `INTERNAL` | `45b1b5ab4bbb753de38aba41794e38fb7288e419b342f3703011049a6a79757c` |
| `app.odometry.reset` | GATEABLE | `1.1.0` | `INTERNAL` | `d758dfaea18a0105356e9a07341ad11eac98b34860229786a0750d2b4c326ff3` |
| `app.odometry.sample` | GATEABLE | `1.1.0` | `SENSITIVE` | `86e2cea7387f2af9dbaf8d905ab8c144e18b573350e5b5b9c8d6b552dd89defd` |
| `app.odometry.status` | GATEABLE | `1.1.0` | `INTERNAL` | `60f00457f9d9cc421a2528a350826709430d658bdea773f7cc8dc63e7f85edc3` |
| `app.parameter.get` | GATEABLE | `1.1.0` | `SENSITIVE` | `d1b4b9cdb6cbbb8c718bbe09c22ed8f7bc3b9536863dfea09346be2ee1239e76` |
| `app.parameter.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `32c846e424c36da5381ae3f29c16c847a485c17598abcb6da73c49ccb77802fa` |
| `app.parameter.list` | GATEABLE | `1.1.0` | `INTERNAL` | `50fba9595a5d5beead4a4525989b2d79a5b9b6cf84e7ea2f995f6c71bb223bc4` |
| `app.parameter.validate` | GATEABLE | `1.1.0` | `SENSITIVE` | `ac2be971361897f39ed6cab74c5136e7ef97d7dcb81a89c19a2ba62265736157` |
| `app.regression.cancel` | GATEABLE | `1.1.0` | `SENSITIVE` | `4cccd1cd98262b23c0d1669be3f32472992f2fe0a56c37d6cbbc513e74eb434c` |
| `app.regression.plan` | GATEABLE | `1.1.0` | `SENSITIVE` | `f1735a5ecdd8d860464951547150d5f2c47aa07e3ad246f8042c39992b1b85a7` |
| `app.regression.result` | GATEABLE | `1.1.0` | `SENSITIVE` | `07bb740fc7d574ad98fedc6ab3397fe2413946f99a1fff34f7d82a99865fb0ff` |
| `app.regression.run` | GATEABLE | `1.1.0` | `SENSITIVE` | `343e593306d4781a3cdd0a72ecf62758f5accc949c5f19e35a6b3b81e4d4f819` |
| `app.regression.status` | GATEABLE | `1.1.0` | `INTERNAL` | `6460ab6ab058f2fb39d08b020c397dbfc8e22a25230c5fdf5b74d252bf708831` |
| `app.robot.discover` | RELEASED | `1.1.0` | `INTERNAL` | `5f11fb3d5eec90bb0dc455d4671283b38e4e9a7be97b8712c0e8d9ce62ef2fdc` |
| `app.robot.health` | GATEABLE | `1.1.0` | `INTERNAL` | `644ef6b4b8c184734da963978fd4313dd0223b50262d0f2af57717adfc7b0106` |
| `app.robot.status` | GATEABLE | `1.1.0` | `INTERNAL` | `01628d2dff00087fa44e7cc74facd2b09570b628c193224b0763249e900869ba` |
| `app.safety.approval.status` | GATEABLE | `1.1.0` | `INTERNAL` | `5958a25ead1884a594db271c8c28f216bbdcb50ddbc4f7d8a37358d318669d55` |
| `app.safety.emergency_stop` | GATEABLE | `1.1.0` | `INTERNAL` | `913ee5df22bc5f7d42800422d55ff9e3d62c18e9f2b822e408319a8e33140ffe` |
| `app.safety.interlocks.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `22c2e4256a115f07c3b2e5dca80e4d07056f99f44a65755b649ac0d65030909e` |
| `app.safety.limits.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `ac615dedfc9768361bf63552ec4917a3004c9cc8d5e9fde1bc28688603dbb060` |
| `app.safety.protective_stop` | GATEABLE | `1.1.0` | `INTERNAL` | `67675af752bdab6e32402857ee5cd5f24df8c1389805622dbea5bf349c1c1f84` |
| `app.safety.status` | GATEABLE | `1.1.0` | `INTERNAL` | `e272fe99fcb7876d60b951b2abded8278be9ed71484bf29c3af4577379e6fc28` |
| `app.safety.stop.clear` | GATEABLE | `1.1.0` | `INTERNAL` | `67b5302d17ff6dae3e8511f98aa0a8e044fc2d0ff34baa77f5dc69ac484d5de2` |
| `app.safety.zones.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `a43fa770ff180da2ec50364f342253164ada72e57467ee0bd5e1c20579321912` |
| `app.state.snapshot` | GATEABLE | `1.1.0` | `SENSITIVE` | `7ea3044ded11f48a5438460135367d46ca220ee577953b5aa0159b9db6d2c283` |
| `app.state.watch` | GATEABLE | `1.1.0` | `SENSITIVE` | `9209431a857de3afd175e0c3e23d5536d50766d781dc607ff444b4e948272dba` |
| `app.task.cancel` | GATEABLE | `1.1.0` | `SENSITIVE` | `1d7b1d83de6791e3285e4423641a1879615257a074ae711c95e5568f00d2055c` |
| `app.task.describe` | GATEABLE | `1.1.0` | `INTERNAL` | `bc3f6bd0a7071bff3a590db24288423339ec2b98fc92a7933c3e87f1165d721c` |
| `app.task.list` | GATEABLE | `1.1.0` | `INTERNAL` | `5073526000af8746275dd4a38fe895ecc8cb6fb1acb9cd3bdf21e861f4ce224a` |
| `app.task.result` | GATEABLE | `1.1.0` | `SENSITIVE` | `6f6275ed6996ee975464d352040c8566e3eae4c9433fa4223ee8df67a14ec670` |
| `app.task.start` | GATEABLE | `1.1.0` | `SENSITIVE` | `1e67c1dbe0e4deda3d632e71ba8ed44d63b23b5f6d61370c0c9be5473e492120` |
| `app.task.status` | GATEABLE | `1.1.0` | `INTERNAL` | `40a97d9676e08c680e0896ef80aa3d937d1a58143fd2eebcb787335511ea5fd6` |
| `app.telemetry.export` | GATEABLE | `1.1.0` | `SENSITIVE` | `810d5a79b4720ab2f851bfaab45792709709d62dc600603ffd264c6ff0845c19` |
| `app.telemetry.snapshot` | GATEABLE | `1.1.0` | `SENSITIVE` | `921420a7712791d801de2dc09f0919eccecb6931723813c78bb05c1c38d26c41` |
| `app.telemetry.watch` | GATEABLE | `1.1.0` | `SENSITIVE` | `e731c3ac65a21a63de30a5172a9926457679067d6268a03d4f50fb998d13eb9f` |
| `app.teleop.velocity` | GATEABLE | `1.1.0` | `INTERNAL` | `513faf38f20bf0be719ffc66c5af9a92cea7ec6c902832a6eff571b0994f56fe` |
| `app.test.cancel` | GATEABLE | `1.1.0` | `SENSITIVE` | `5cf85f8e4b48a5f909bdf9fc231bb07871dc361398f424cec8b11ef3a22ed24a` |
| `app.test.describe` | GATEABLE | `1.1.0` | `INTERNAL` | `46065838f30271090d75a38d78dd3cf4dd10a0988eee07b2b1dbafe8c98ae5fc` |
| `app.test.evidence` | GATEABLE | `1.1.0` | `SENSITIVE` | `da3e3df81159e9f33ba39dda2255b38877ec8b3efd96efc39d9877d0d94bc6cc` |
| `app.test.list` | GATEABLE | `1.1.0` | `INTERNAL` | `b240bf98945ef6af5375df1e491552bea2faa1f2cd9bd53021bfde3a97784f58` |
| `app.test.plan` | GATEABLE | `1.1.0` | `SENSITIVE` | `f3e3277f573e68d8808c36b7465a076808f17ef68f079a6572357bd5dc6d28bc` |
| `app.test.result` | GATEABLE | `1.1.0` | `SENSITIVE` | `57f83deaa2baae8b7d439147b140ddd424988abb3f1128de2d29cc72ce6b1ec3` |
| `app.test.run` | GATEABLE | `1.1.0` | `SENSITIVE` | `ef88f098f05122d34101c7175082fdf7415ab355f810ce25235d1ea56ac87222` |
| `app.test.status` | GATEABLE | `1.1.0` | `INTERNAL` | `77b0bda1e8301c6ae41bd8aea675123bd2b09b50bfa9ff804c3e68221cc4ca0f` |
| `app.tuning.candidate.evaluate` | GATEABLE | `1.1.0` | `SENSITIVE` | `5aadf2824cda826a0a3bd3376d87ce88ba20818d87a9e8ca8e8f94d20b56eaf7` |
| `app.tuning.status` | GATEABLE | `1.1.0` | `INTERNAL` | `b8fccf97e567becbaa314d11f3a53d753b8429fb4ebab1eeb72e45f7c4c8bcba` |
| `checkpoint.create` | GATEABLE | `1.1.0` | `SENSITIVE` | `4d6f3ed87280af28b4596055bef52040a66c1b80b739d6962b9909d9b2d78ce5` |
| `checkpoint.list` | GATEABLE | `1.1.0` | `SENSITIVE` | `d8b6ed7fa7b95ec8efed606228bb7a889e5c898df0d8186cf3fc8199e12a3c4a` |
| `checkpoint.restore` | GATEABLE | `1.1.0` | `SENSITIVE` | `f33185eae2537485ee50848067c53f0252410367141bb0bfdd6b7d640a738f49` |
| `episode.export` | GATEABLE | `1.1.0` | `SENSITIVE` | `2c1138b4e5999015a383f2be19cfd4e42c67ce5df5b9035ee85ef07127191cb3` |
| `episode.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `3c8eded61a1c554817e73d319bdd8b15ea673b0ad914643aed072010bf0c2b6a` |
| `episode.list` | GATEABLE | `1.1.0` | `SENSITIVE` | `e7b21b965185a994702d48ac05c505b8c494ca9e53d35ec8922ebec5103e8ecc` |
| `evidence.resolve` | RELEASED | `1.1.0` | `INTERNAL` | `f5b4b63d2916476ffc5d209d03361abeb3ce612ad4bfc95e6f07646d3c7ace8b` |
| `hw.actuator.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `1efa1762cafd9ba880523d48fa84a9eae4127351b6a6298af48ce6df5e0fcae6` |
| `hw.actuator.list` | GATEABLE | `1.1.0` | `INTERNAL` | `d3184f9e1292c4836224bedd653213c9a17213fbb81a9b1deff9272fc4a4a0e0` |
| `hw.actuator.status` | GATEABLE | `1.1.0` | `INTERNAL` | `97bdbc322c026889f60df4dfbf659c26d8ce9f44b4a6a71682c901bfb03776aa` |
| `hw.bus.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `6cfa28e62ac93b1b7b4ff1bbe3cfb41b1d83c71a0068d090c08433855f6d0b9e` |
| `hw.bus.list` | GATEABLE | `1.1.0` | `INTERNAL` | `1fe88a6aa8f0859a72640d3ec284c1b8cde2f501a84b9a558f97e377df27d2b3` |
| `hw.bus.scan` | GATEABLE | `1.1.0` | `INTERNAL` | `a231e8cfc4b90a17b7e3e4a73a5afbdff3649e76ef31b74dd6a17a41dea38892` |
| `hw.bus.statistics` | GATEABLE | `1.1.0` | `INTERNAL` | `6a614d58d6baa8c10e731cd5441145364e4a7b5af152fba294ebdd34bb05c2bd` |
| `hw.bus.status` | GATEABLE | `1.1.0` | `INTERNAL` | `26f4a674ad138e46c8e5fd8376b9c13ea9fb51469a00d125ba7d494eb998d237` |
| `hw.clock.status` | GATEABLE | `1.1.0` | `INTERNAL` | `7ebfc89e5cd8e56a1d1ca998f4c12f7ccc3ea897951838ec189636532c814893` |
| `hw.compute.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `a493693c3d1ad87b5d165e34c0d12415ee7da273c4a4172368ffb20f5b4d2c6f` |
| `hw.compute.list` | GATEABLE | `1.1.0` | `INTERNAL` | `4346905c6696982f50764cd9ea8cd45bc45a957f5e9323734c1efdd577ace3a9` |
| `hw.compute.status` | GATEABLE | `1.1.0` | `INTERNAL` | `2a952cb5a6b38768069b0d281671ca6a2d6c0223cc74706f38b7141afe8484ed` |
| `hw.firmware.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `8a976f41bbc69b8fb369a0268693c8f4ef1fb085d2f97086a51f6f85b562fa04` |
| `hw.firmware.list` | GATEABLE | `1.1.0` | `INTERNAL` | `0877492877c7fcfa18973edd0e2167c9ef4b132feb9de30e49bd973d367bbb41` |
| `hw.firmware.verify` | GATEABLE | `1.1.0` | `INTERNAL` | `5888127c286e74a38d9a842c0360929156caa98cfab1088ea2aaa141c6852e91` |
| `hw.inventory.scan` | RELEASED | `1.1.0` | `INTERNAL` | `aa48f8f709e450a4be1a37285dcfb1a719275705c9601700c9054381383cc9d0` |
| `hw.power.battery.status` | GATEABLE | `1.1.0` | `INTERNAL` | `a7cf734e909878542beb861526cef20bdc37e13ae2fb20f43b6dbb39d8cadfb9` |
| `hw.power.rail.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `194c7e6d95a9c457d609ef49c20a65ddf3569bd40beaac0eca64e00a94556e27` |
| `hw.power.rail.list` | GATEABLE | `1.1.0` | `INTERNAL` | `9a5a367f19a3353937a1b45d9127202726077b3fee82c0ea46f1600cebc1a1ff` |
| `hw.power.status` | GATEABLE | `1.1.0` | `INTERNAL` | `13b6e924a426e22342f4bea0394910aec55e6c75b0448034c30e608df26cddc0` |
| `hw.sensor.inspect` | GATEABLE | `1.1.0` | `INTERNAL` | `d6897bc5b7a89cbee258141dfc9b8db4f85fec75a42ac9f335177dad1d4c4dfd` |
| `hw.sensor.list` | GATEABLE | `1.1.0` | `INTERNAL` | `5d772f8c1d6bff7f2e29ba712a7c2863c5164422aca2f3a50f1c018c65fccd4c` |
| `hw.sensor.read` | GATEABLE | `1.1.0` | `SENSITIVE` | `bb5395ddde0cce4600ad930b9b36f0489bef7fff60a0f10ca3e540f087d49ce5` |
| `hw.sensor.status` | GATEABLE | `1.1.0` | `INTERNAL` | `8d3596aa75239d7875f1ced5baf5d72ca7156911f44a73f65516479588837dce` |
| `hw.storage.status` | GATEABLE | `1.1.0` | `INTERNAL` | `7a1a644898d6b5d742ebfc4ac5cf618bf5c861e19da9b2c923be5e7bcb42e72e` |
| `hw.thermal.status` | GATEABLE | `1.1.0` | `INTERNAL` | `969c689c8d7383a57e493199af6f02a9cd8d714c53b32b1b6194ed00e1564e66` |
| `linux.binary.describe` | RELEASED | `1.1.0` | `INTERNAL` | `e8d7925c3c08f14f4c246891ef8175a84a87f85ef04aca7efefd95086d2a69f8` |
| `linux.binary.verify` | RELEASED | `1.1.0` | `INTERNAL` | `4390b04b802c4fcd9a7fea41fa5e894c24a9271b4e36ae802353adb8a3d5db9e` |
| `linux.cli.probe` | RELEASED | `1.1.0` | `INTERNAL` | `cd0ae504fed4b20d8b3e4e7c0d9274be90bd02946a970579000752242398b81c` |
| `linux.config.apply` | GATEABLE | `1.1.0` | `SENSITIVE` | `7d6b627204c0ce6e4b35c3e78f2f89d8e4881afdd716e868d2079c960627a79f` |
| `linux.config.diff` | GATEABLE | `1.1.0` | `SENSITIVE` | `baeead7f2112ff79e1787b97455e113c0fcf6ac1f8c58d76c25bf70e639c1415` |
| `linux.config.inspect` | GATEABLE | `1.1.0` | `SENSITIVE` | `f650ac7536b2ac2632a99a14d3832624c5ae1907250fed06005b6b6ee18ab82e` |
| `linux.config.locate` | RELEASED | `1.1.0` | `INTERNAL` | `9c723f3143a60547ebf395bcf8241cd0a9982f051e1ce74baac7be5c9366f71a` |
| `linux.config.rollback` | GATEABLE | `1.1.0` | `SENSITIVE` | `bb609ca4ae4dac380e5abfb9a8218842960b06681d9f639a08ef9c6a709d29a3` |
| `linux.config.validate` | GATEABLE | `1.1.0` | `SENSITIVE` | `9f81c9d8a4c095e684dff08bf1e0294adf0517d1365273d79a49c36d0f1c6cc5` |
| `linux.container.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `9791e58c012c96ef5e44513800b0a608b5e8ec2192f87fff7e14e7a3724307e0` |
| `linux.container.list` | RELEASED | `1.1.0` | `INTERNAL` | `0275ea0eb987022c7d448ebb4f42754f75d1132926eb4665e99780ab970d3a8a` |
| `linux.container.logs` | GATEABLE | `1.1.0` | `SENSITIVE` | `b609694b91002ccbf1a3109edc8e0d0af4739076269a56f95af17ee416af0f8f` |
| `linux.container.restart` | GATEABLE | `1.1.0` | `INTERNAL` | `d20ba9a0cdf610a7b5df1ead47840a70236d564be9db5d55cc6bad7f1d059033` |
| `linux.container.start` | GATEABLE | `1.1.0` | `INTERNAL` | `d37fa16af97d1006a5065552e2e4bd4137008a17d7db6c40a0c2d05fd0da01d2` |
| `linux.container.stats` | RELEASED | `1.1.0` | `INTERNAL` | `c3134dcda1b9a44949c0a20ecbf6f953691ab52f91477ea2225f890f1a80687f` |
| `linux.container.stop` | GATEABLE | `1.1.0` | `INTERNAL` | `78baee45010be3df6dd8d4741b275ee0fc5eecb7c8d0ecb3dd62fcf2b21ea833` |
| `linux.file.hash` | RELEASED | `1.1.0` | `INTERNAL` | `1db2450e5dd43d55064f66360715dfcd0b9683dc1af7fffca570cce2704cedbc` |
| `linux.file.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `2a9012809d63f0c71810af77b9adcd7653b193b27c981d622b537c5c1a0098de` |
| `linux.file.list` | RELEASED | `1.1.0` | `INTERNAL` | `6eba479056df742114232594809092b5df949b69a9dd06df65480c1e27757ea8` |
| `linux.file.read` | GATEABLE | `1.1.0` | `SENSITIVE` | `0683ab04070244d590ea63ad20dfbdbc164dc0053f0de58c8d8eaa59f5bdc858` |
| `linux.host.inventory` | RELEASED | `1.1.0` | `INTERNAL` | `6c021bfe8274369e46bc07498c16148156759f4b7b9e1182c675b9debaf5222c` |
| `linux.host.reboot` | GATEABLE | `1.1.0` | `INTERNAL` | `45a0f4aeceffbb62737829ce4a1cc42a6f5d7b905dfcbdc34db4225c218a6549` |
| `linux.host.shutdown` | GATEABLE | `1.1.0` | `INTERNAL` | `1a4825f74953feed48a341b0cd5de0a7863d316041c809f70a78dd08663da1d7` |
| `linux.host.status` | RELEASED | `1.1.0` | `INTERNAL` | `b020964455d9cb5f4f65dbc42ee62710fd5b1bc01cf05c2c61c8a064a63ab3fa` |
| `linux.host.uptime` | RELEASED | `1.1.0` | `INTERNAL` | `b867ba35d98c14519275e9b1f05da6aaa4a5968b0c137083e3c03fc2115b03f7` |
| `linux.log.follow` | GATEABLE | `1.1.0` | `SENSITIVE` | `5ec70ab86f56f946bde25f825974c9b2b1556b88218008509c9239c3093be167` |
| `linux.log.query` | GATEABLE | `1.1.0` | `SENSITIVE` | `4a6ccd345a9019e482acf49dbed6a73bfcdf10d1fd467ee07a27448b3f84afd6` |
| `linux.network.connections` | RELEASED | `1.1.0` | `INTERNAL` | `afe1ca7a80366ccc8c047a48be49004ca4e069b0598186bd88388abef427d5ff` |
| `linux.network.dns` | RELEASED | `1.1.0` | `INTERNAL` | `075d95f7b90d757fe3069e68851a3c45a8e8beea731c8f49f55780b293a088ad` |
| `linux.network.interfaces` | RELEASED | `1.1.0` | `INTERNAL` | `77dd7b3b1e7b92d5f7adb7aff6f859b3299dba7cf367b6fde0e8122ac72aa437` |
| `linux.network.listeners` | RELEASED | `1.1.0` | `INTERNAL` | `51dddcaf664e9f13953f7bc8523957c92ee2579b09a797640a620e29c25c98a7` |
| `linux.network.routes` | RELEASED | `1.1.0` | `INTERNAL` | `625a055fbe0539bb1704970f9af5e3b23b8823bcf07eb9fed7c392e0df467ab0` |
| `linux.network.statistics` | RELEASED | `1.1.0` | `INTERNAL` | `ee37dedef093e310b6af329403617db108a01993d0c6e39e0ed8d807c3547a19` |
| `linux.package.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `902d0218061f8278f11b9a2ed85fb554c23c971de858ea0b3cd8f076685b849a` |
| `linux.package.verify` | RELEASED | `1.1.0` | `INTERNAL` | `1e91c0383fc1360ba403805901387e2e8412aa7acb17f2387128c0cfa997cebb` |
| `linux.process.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `f8257b90f31260968f8e6339bdf4acb212d90345f2578eace59a4691ee174ac3` |
| `linux.process.list` | RELEASED | `1.1.0` | `INTERNAL` | `9354dc23fdcc434e0b604788da24892d2edd48b6b87236e3184f4dca6830878b` |
| `linux.process.logs` | GATEABLE | `1.1.0` | `SENSITIVE` | `759b92570e3db9cb7f874de33c95ef40e262c18021e8e64b02948520cfc81fbf` |
| `linux.process.resources` | RELEASED | `1.1.0` | `INTERNAL` | `aaf3385d55891c045157af619a8fc337793b4dceea523ae6d7f728374ec5fd3a` |
| `linux.process.restart` | GATEABLE | `1.1.0` | `INTERNAL` | `b0c4efdc9accfea7340d6bcc4b4508c92edf10af02e7ab9ad1f4172bccb1522e` |
| `linux.process.signal` | GATEABLE | `1.1.0` | `INTERNAL` | `ef365b5526d3ddc5b50d299b88e5f75bd08de7cc1bd7f9bd158627cb9e7e1fdb` |
| `linux.process.start` | GATEABLE | `1.1.0` | `INTERNAL` | `2f97a8a1f7afe45ec1c180f6c43fed52cbf8462186d979796ff0fcfae0f14764` |
| `linux.process.stop` | GATEABLE | `1.1.0` | `INTERNAL` | `481f194980dcc0b2ef23eb5088035a2cdf2d23cfc78f2eeb76143ff519769e2c` |
| `linux.resource.cpu` | RELEASED | `1.1.0` | `INTERNAL` | `5d8e7681d4c1d8518f9482af83591fe6cb94f41a98fae159def0b5aa3dcc5631` |
| `linux.resource.disk` | RELEASED | `1.1.0` | `INTERNAL` | `805a2e7b9bd4f2f7ef2d6818683ed033cf252f19b8f14e81eff2f5a27cef49c4` |
| `linux.resource.gpu` | RELEASED | `1.1.0` | `INTERNAL` | `fbb0f2bb82b30a133f86c41c6fc219d778eb6ee4a1a7f4148fcde97b41010615` |
| `linux.resource.memory` | RELEASED | `1.1.0` | `INTERNAL` | `527924269ed98f4ee8a5a3e6fa9e90f70c4ba12b5e03c5c56a7d7632f57e1cd3` |
| `linux.resource.snapshot` | RELEASED | `1.1.0` | `INTERNAL` | `fb5db5d0e3d387cbaae79bf93cab5192f5f7410764e6bfb39edb99ea480ca760` |
| `linux.schedule.disable` | GATEABLE | `1.1.0` | `INTERNAL` | `19ae1543002b31b18843e9ec009e9b4823e7d1e22411f1b1f7a70741219d22d1` |
| `linux.schedule.enable` | GATEABLE | `1.1.0` | `INTERNAL` | `af4b58116a9d4ae86e0cfeb3d6a032bdc07204208b4516df615faf66672b950c` |
| `linux.schedule.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `f4d4da5ab90f6a2866048f84d8aaabab829da6ac496aaa7fefd3e48d1783f45b` |
| `linux.schedule.list` | RELEASED | `1.1.0` | `INTERNAL` | `70b691637bf47e4918bbeb6249b4766dcdfecca8b36865b4de7c98636452b9d0` |
| `linux.schedule.run` | GATEABLE | `1.1.0` | `INTERNAL` | `7bc25e845864d1cc400bb0d2fb2b7779ef41da8cf85d1fddaa8dcb93422bd8d3` |
| `linux.service.disable` | GATEABLE | `1.1.0` | `INTERNAL` | `8460f0929f3c0f5d91ab41fba437329ed93c343c0f1505c6e48015dd67c7a03f` |
| `linux.service.enable` | GATEABLE | `1.1.0` | `INTERNAL` | `29f5206cae4c8ee28c2f6c2628d41a9e9fad66ac5f9f99420a7dcf03653cbbf3` |
| `linux.service.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `22f003f4e61d1d9d72be3b172c0cb0748e7151d1250ec3e57b2a0a5db6545edf` |
| `linux.service.list` | RELEASED | `1.1.0` | `INTERNAL` | `a53b458d1945e7b60bb50846304a95da2ef5b3b11bc46ee50e1f56c0acccf829` |
| `linux.service.logs` | GATEABLE | `1.1.0` | `SENSITIVE` | `1732536829c06c4d2793d3453be94dbcec8b487d1f52c7b490aaeb9ef27fe9f9` |
| `linux.service.restart` | GATEABLE | `1.1.0` | `INTERNAL` | `aae230addf632fbe4efa1b53a1e8981a12cb4ee3b3422117f32afb073ef589c0` |
| `linux.service.start` | GATEABLE | `1.1.0` | `INTERNAL` | `b9d118a922036ab6d87f0edfcc9bc6106d04d6142707d8cfa04cee690d16f2ca` |
| `linux.service.stop` | GATEABLE | `1.1.0` | `INTERNAL` | `d4743a3ee4caadc2b6c141cef8076b6d5e92572f83283761cc5c36e7378bb915` |
| `linux.time.status` | RELEASED | `1.1.0` | `INTERNAL` | `871fff04d672c097a7b0d44376057686d488e0c616693e4f2be4e092859d8c63` |
| `linux.time.synchronize` | GATEABLE | `1.1.0` | `INTERNAL` | `bfc2b579198caea08a292ce391f8a85635dbb62432ae7e4e1fcd24284e36ae0b` |
| `middleware.graph.snapshot` | RELEASED | `1.1.0` | `INTERNAL` | `88957bf5cd1e2089e0476fd1da19b9cd9ddbec8b75ec70e1ee65192bac44af58` |
| `middleware.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `438145c10f91d9c40d41eafc40cc7a16cdf9fdb119b23705e6d0e1de537e4842` |
| `middleware.status` | RELEASED | `1.1.0` | `INTERNAL` | `d5608bb6d4ad3af5b09ac009e3bd03e6af5332fd31e842b5e114d2ce0ee00a2b` |
| `ros.action.describe` | RELEASED | `1.1.0` | `INTERNAL` | `3dc0728ff5d0e82f50600164be423b4ecf1d382ca965a14edbb6b7c3360190c0` |
| `ros.action.list` | RELEASED | `1.1.0` | `INTERNAL` | `cc8150b3f4e3ae191409a1e3a52072ca8373fd80dceeed468c1f627fbeaa87f9` |
| `ros.action.status` | GATEABLE | `1.1.0` | `SENSITIVE` | `856b71ddc791585a13d977733c32192205f240443b0e21b604baead19ad7e4e9` |
| `ros.bag.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `337b30b8869d6e0465739296ba15055b04adf74349a3fb58a8fd6d5683e9231e` |
| `ros.clock.status` | RELEASED | `1.1.0` | `INTERNAL` | `6695485c7542f2fe47c482d8464127fd46b6541b521c529ef428f0a31f44c890` |
| `ros.diagnostics.snapshot` | GATEABLE | `2.0.0` | `SENSITIVE` | `6122394914a6359a1fc9751050d70571779da37027013d1d6b8c5e4af04f29bc` |
| `ros.diagnostics.watch` | GATEABLE | `1.1.0` | `SENSITIVE` | `6546b19435363b1b8eeb24a61521ec44b2bc09bda26d28e3fab3814675c18555` |
| `ros.graph.snapshot` | RELEASED | `1.1.0` | `INTERNAL` | `cf294e45e10b3e67ac94b2797bb2b654af2205523b12bd120beb42c9cea31607` |
| `ros.node.activate` | GATEABLE | `1.1.0` | `INTERNAL` | `f443c219e5f7bd95e904107990a6ddc75919fc94932d1f1d48c9e4760131fa6c` |
| `ros.node.deactivate` | GATEABLE | `1.1.0` | `INTERNAL` | `fc20b82c716c1dfdeebb1d34888590eb03b803ba1e79298bbf2b3a3dae02fa20` |
| `ros.node.inspect` | RELEASED | `1.1.0` | `INTERNAL` | `d7e5ca70c23e291adc2c27439626d8ea240555885169d8158207aeb828c83f55` |
| `ros.node.lifecycle` | RELEASED | `1.1.0` | `INTERNAL` | `96f7f7c31d76f89afb5586d2995e62516449521bbbe27e8e6e6185abce7554ef` |
| `ros.node.list` | RELEASED | `1.1.0` | `INTERNAL` | `044c490223a88be3e4010772da8a03617a13a9ab999680ad8de0e0623af2f4ad` |
| `ros.node.status` | RELEASED | `2.0.0` | `INTERNAL` | `e71215c8b152b67dca0814acaa27bd4edc36f48d7e481115e7e723587afb5b21` |
| `ros.parameter.describe` | RELEASED | `1.1.0` | `INTERNAL` | `1d7d9311c7426e9457822cf933582872ac99fc63e39715ba2d02f319599d7868` |
| `ros.parameter.dump` | GATEABLE | `1.1.0` | `SENSITIVE` | `1ebe9c8db1467a30d7e6618ce94536fabde340e7daed37bdbe1830c2b4dbcef3` |
| `ros.parameter.get` | RELEASED | `1.1.0` | `SENSITIVE` | `84bd87e5bb0115441c4a0764004e63d3d13a5c85a08a09137c43ba83872489ac` |
| `ros.parameter.list` | RELEASED | `1.1.0` | `INTERNAL` | `69b0abbfa962c9f5c002ee7e81d5b0d5e41c6e4d2022cff5cd1231dd1e886563` |
| `ros.service.describe` | RELEASED | `1.1.0` | `INTERNAL` | `d62882012d854fda44c22ff8b9d6dccaff181d8a9d84d1fbbf7be74c86928635` |
| `ros.service.list` | RELEASED | `1.1.0` | `INTERNAL` | `f10a08655f32d32b5e616d5c992ebd700a0a16d27944ebc77b8e7c7705d9b71a` |
| `ros.tf.lookup` | GATEABLE | `1.1.0` | `SENSITIVE` | `1cf7f81868495e3030882ca480b64a10a294081d8cc6eddebf9bf488736abf9c` |
| `ros.tf.monitor` | GATEABLE | `1.1.0` | `SENSITIVE` | `428c33833e90b78c4495a45aa1a64b5aa6bd6dc70bb7dc0b13f2fde3f027ea96` |
| `ros.tf.snapshot` | GATEABLE | `1.1.0` | `SENSITIVE` | `6bca07a18125d75f37eb4ab7e91b9ee1005f8cf53b52a034a35b757230e9218a` |
| `ros.tf.tree` | GATEABLE | `1.1.0` | `SENSITIVE` | `4d4dc1844b0bcb51687ec4b427e6adc00b45e479310cce811e655e9532bd916a` |
| `ros.topic.bandwidth` | GATEABLE | `1.1.0` | `INTERNAL` | `faa27a7da100f8833814b4cfc1d2a8370fdae92a75794a9610b73099eb7aa6a9` |
| `ros.topic.describe` | RELEASED | `1.1.0` | `INTERNAL` | `b4e8f60ca6b9add7e4e95c52aa9036f259ed598300dbaf299fb33d61b3e4c53e` |
| `ros.topic.list` | RELEASED | `1.1.0` | `INTERNAL` | `715b718dfcc2bfb8e9b72ed118b9be588d6ad5333e80d0ce2322ce011755fb09` |
| `ros.topic.rate` | GATEABLE | `1.1.0` | `INTERNAL` | `88a926ba59a2a8b24cc5524bbb189b3f1834956c05bb7f99b5f632a8b53e0e21` |
| `ros.topic.sample` | GATEABLE | `1.1.0` | `SENSITIVE` | `7e7949f309d5de96ac4ac0eac39a7fb5f2a08667b5e70db6a48d8fcf7a38961d` |
| `runtime.health` | RELEASED | `1.1.0` | `INTERNAL` | `f334aa1fb19fd393b5656ec6439c24d8f2086f32e71e76a8f8dead8318448163` |
| `runtime.version` | RELEASED | `1.1.0` | `PUBLIC` | `bc7070c95666b06970525b83c3ba15a2b1f8f8ac452e0a229dc6919758d2e96d` |
| `state.graph.query` | RELEASED | `1.1.0` | `INTERNAL` | `213faf9ea18a1accd2bef6b49c48c0f0d39a852fcb018c6b3377f22e7f552f5e` |
| `state.graph.snapshot` | RELEASED | `1.1.0` | `INTERNAL` | `561dd662b9f7a272ea3375f9bb347788311a940b350c9b8d910cd832d62a3329` |
| `tool.catalog` | RELEASED | `1.1.0` | `INTERNAL` | `d46b5cccb0b1697b519eb154993a10add63dc11c739037b1f3eeb5b4bc318e0f` |
| `tool.schema` | RELEASED | `1.1.0` | `INTERNAL` | `76d041c3ca220820a2e65dc55557b638c4cb4b5b9c9a8165fb30ccde214c0055` |

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `2360007d6f4f4d6747ba2486fb72391e8d4943ada52b9a59f17185ec1fc1ef6c`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `9e21576b94327507ac318e15c0e773a7dc0bf691fbed95c325cc8fac44aeae87`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `2ac48c3ca6d61ad2843eaa46ed335fc36ef7c8059d34b0a9dfa99b8a25a707a1`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `1648e823c39812a9fe2d525af5949f944f7b85053b5f60b053551b97f4c6793a`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `aae319a905c3bca555ae967d5196b9911cf8a619b9adc2feb4386fb0b5bd0ec8`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `4bfd1e0049bbcaf8e38b327ad10474d1de4ca0338deec53838e72a4285da487c`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `07b446ad7f7592b53907073d24e9d0d814d69963bd1439ea05461beff65c5849`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `c96ae66314c186f7612289542d38054bdb4dcac73bf06c2e3c54b6f9c867dcde`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `0755ebedfca8b5a8cb198961b83222e9c3b93a323c4596496cbbb84de33e65f0`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `fc662b5d33465eb5b12e3a8559231fd7f0edaf1c8466d9dc6b41e472971d1cb4`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `89b4c805b768426b8954f240bb188d81c53a1410c068687140902fe7d55a4c83`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `801df85008c188e05820c2b7e310b48a901fe4f7528486588341f48d7597c421`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `a61ff29823e8dfc945ce5034ea0f01eba591a18930df6ca6044292519668d589`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `c0ffaad9ea7fb3748dc4c1baa7ac3ea04c4ac0b315db4e2d5073304d82935f3d`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `2745aeff8db907c721063d78fda952e936985ca75f6c4e286408bbc6c53e9ce3`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_PLAN, INTERLOCK_BLOCKED, BUSY, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `34c6c3e2f3913b5e5a9cd5ad484023d8ddb77bb8ae69ea9768f573d130bc3550`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `bcd742d2936be84e3557928d6874cf0d55fb7feb680e4174c24d1127284aa1f2`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `6719c7f1dbd1908293d49dcf0b64d2607bc63d944cc04ca80d39605101c90ed0`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `2e3373c872fc153dd12fbb988cf9457d6fc23d1961f532c80b08a21c32935331`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `dc3ece5497392b493d3bb6ed3b353e4ed230b9c596f11f83c501b8f2801aa981`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `67cec17a19623912fb56846198b664151c779e96d1c8cf2dc58b25dd46593472`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `ce6d31ed0cdb83e61aa0afed28cf0815a95b1a5aa9e87fbb728212c2f554e06a`

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
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `363bd8d76009821ef77b7faace3a4456270f90ab5067ee1781607fbbd0c51965`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `4b050fa8d74d57359568f3a729e074b579031f5e4711f57fa8a5730795e6f99a`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `26b84de8909b800322caf20d1a0fc79913aa00aacba8f9fc1f5a6948d05fb549`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `8c12bd3de93d4aed705f197bb3016a6c5f26afe8ace15d5fe71935124928d832`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `ea0472c4c16333f64a46484114e395753d9690cb30f85ecd6cdd31c40921e9fa`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `711ba8512b3095c6251abdabfec2dcf4c67eb98d9144c184893155ad9294a9ad`

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
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `fe0ee487bfcecf86f98e80617b751689e05b308f8823002a632babec18066477`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `e99054394d8ceb219c88fa830fabffa3f07f46e7b5bdeb60d01e7465e518bd3a`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `a0ae11e7c079174f23f71eef1190eaa341fc691fcb429cdfeb56a2ae36d05677`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `d73b9ce5680ab0ae8d1538d6d44185ea63ecc9f70ea6bbf8d3a5afb5b149ec16`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `e94c564050cf03cb714f97e7870373275acf40082279ca27b36707e39c336926`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `cfa165225acf315dfec9b436eea858338eb59444bfa7b9ac60e4faec27df1d51`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `9d1ec2cc089e762ac2a2b8f2fc2a39719b0fd7c297e1120bf39be73a23473f4c`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `bab27878079b6199173d0527c5930b3331236ef410e200a0acb0299394f81a5e`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `3a7ae4c05a97e2b3485b7c8b185cb34a963ee6973fcd8d407254b9d6c35e83fc`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `29bcec8471902356a17c7673ff5c18b84933a4b16972967f6dc6663a6d2339da`

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
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `b330371e02385a9d13cac6641b9a140dc71aa14c0a8a0b14ab69edc8d8c98a69`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `d87d8d81e7b4ffc35cc275d5bc9c62df2d9d9dfe5e836efb876848f8d0500387`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `ca4b98b12b9b99f09c38e4cdc2d79f7d1ac3f682bb0d5fde8b0508e2cc90d99f`

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
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `b810b4393ca7e5f5c9f3e537275543f534350def904496fb91011270d3028415`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `d34b3e97c307437ad8772d3bf13e9f5172085c2864b7c5d03f58111a79f4ce70`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `dfee965210d933094c96c8063dfca5d802ec7e6aa805607277687a029e8379f4`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `e648f8d93c3d76a5ccc7de22b293c5bd4cdebd4bd635e0c23bbe9256d73e531d`

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
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `034a07416e6e4715fada56e2907323d4d536257ef41a84f0fa4c72f7dfd13e45`

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
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `a974ab5b92675c6d1d47a21b414429296717402334fc1c667c89511988250d0f`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `346c9343b63398a24891f840bbe9b3ceb8c8dac6a70a9573697ec41ee3628fc9`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `347f1bf4362908ca33e62b40a27220671a51696cc4b5be1139b5529249f7fed1`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `f6f54bd9d9e510df928ef79168258b0d8f4e7fcee011127fea9d85ba83e08111`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `e5466ee2fc52571fe11d36f7ee085e0484a6807b9ef11f2888b78ce8a03f3878`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `e6997ffa709c5ec331919d087926079d40f5ac8c68089f808276c1af489516d3`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `2ef63291d2ff86a1b98996fe2c05f9105595573043daa3ebe7b7fbf9108f13a4`

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
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `b98a5d0b9e88a5897c647a23956c426ea599077174f2bd4fc9bd13604f9f4c99`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `45b1b5ab4bbb753de38aba41794e38fb7288e419b342f3703011049a6a79757c`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `d758dfaea18a0105356e9a07341ad11eac98b34860229786a0750d2b4c326ff3`

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
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `86e2cea7387f2af9dbaf8d905ab8c144e18b573350e5b5b9c8d6b552dd89defd`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `60f00457f9d9cc421a2528a350826709430d658bdea773f7cc8dc63e7f85edc3`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `d1b4b9cdb6cbbb8c718bbe09c22ed8f7bc3b9536863dfea09346be2ee1239e76`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `32c846e424c36da5381ae3f29c16c847a485c17598abcb6da73c49ccb77802fa`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `50fba9595a5d5beead4a4525989b2d79a5b9b6cf84e7ea2f995f6c71bb223bc4`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `ac2be971361897f39ed6cab74c5136e7ef97d7dcb81a89c19a2ba62265736157`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `4cccd1cd98262b23c0d1669be3f32472992f2fe0a56c37d6cbbc513e74eb434c`

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
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `f1735a5ecdd8d860464951547150d5f2c47aa07e3ad246f8042c39992b1b85a7`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `07bb740fc7d574ad98fedc6ab3397fe2413946f99a1fff34f7d82a99865fb0ff`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_PLAN, INTERLOCK_BLOCKED, BUSY, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `343e593306d4781a3cdd0a72ecf62758f5accc949c5f19e35a6b3b81e4d4f819`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `6460ab6ab058f2fb39d08b020c397dbfc8e22a25230c5fdf5b74d252bf708831`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl app robot discover`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `5f11fb3d5eec90bb0dc455d4671283b38e4e9a7be97b8712c0e8d9ce62ef2fdc`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `644ef6b4b8c184734da963978fd4313dd0223b50262d0f2af57717adfc7b0106`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `01628d2dff00087fa44e7cc74facd2b09570b628c193224b0763249e900869ba`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `5958a25ead1884a594db271c8c28f216bbdcb50ddbc4f7d8a37358d318669d55`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, NOT_AUTHORIZED, PRECONDITION_FAILED, OPERATION_FAILED`
- Contract SHA-256: `913ee5df22bc5f7d42800422d55ff9e3d62c18e9f2b822e408319a8e33140ffe`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `22c2e4256a115f07c3b2e5dca80e4d07056f99f44a65755b649ac0d65030909e`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `ac615dedfc9768361bf63552ec4917a3004c9cc8d5e9fde1bc28688603dbb060`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, NOT_AUTHORIZED, PRECONDITION_FAILED, OPERATION_FAILED`
- Contract SHA-256: `67675af752bdab6e32402857ee5cd5f24df8c1389805622dbea5bf349c1c1f84`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `e272fe99fcb7876d60b951b2abded8278be9ed71484bf29c3af4577379e6fc28`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, NOT_AUTHORIZED, PRECONDITION_FAILED, OPERATION_FAILED`
- Contract SHA-256: `67b5302d17ff6dae3e8511f98aa0a8e044fc2d0ff34baa77f5dc69ac484d5de2`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `a43fa770ff180da2ec50364f342253164ada72e57467ee0bd5e1c20579321912`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `7ea3044ded11f48a5438460135367d46ca220ee577953b5aa0159b9db6d2c283`

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
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `9209431a857de3afd175e0c3e23d5536d50766d781dc607ff444b4e948272dba`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `1d7b1d83de6791e3285e4423641a1879615257a074ae711c95e5568f00d2055c`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `bc3f6bd0a7071bff3a590db24288423339ec2b98fc92a7933c3e87f1165d721c`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `5073526000af8746275dd4a38fe895ecc8cb6fb1acb9cd3bdf21e861f4ce224a`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `6f6275ed6996ee975464d352040c8566e3eae4c9433fa4223ee8df67a14ec670`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_PLAN, INTERLOCK_BLOCKED, BUSY, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `1e67c1dbe0e4deda3d632e71ba8ed44d63b23b5f6d61370c0c9be5473e492120`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `40a97d9676e08c680e0896ef80aa3d937d1a58143fd2eebcb787335511ea5fd6`

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
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `810d5a79b4720ab2f851bfaab45792709709d62dc600603ffd264c6ff0845c19`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `921420a7712791d801de2dc09f0919eccecb6931723813c78bb05c1c38d26c41`

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
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `e731c3ac65a21a63de30a5172a9926457679067d6268a03d4f50fb998d13eb9f`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, NOT_AUTHORIZED, PRECONDITION_FAILED, OPERATION_FAILED`
- Contract SHA-256: `513faf38f20bf0be719ffc66c5af9a92cea7ec6c902832a6eff571b0994f56fe`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `5cf85f8e4b48a5f909bdf9fc231bb07871dc361398f424cec8b11ef3a22ed24a`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `46065838f30271090d75a38d78dd3cf4dd10a0988eee07b2b1dbafe8c98ae5fc`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `da3e3df81159e9f33ba39dda2255b38877ec8b3efd96efc39d9877d0d94bc6cc`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `b240bf98945ef6af5375df1e491552bea2faa1f2cd9bd53021bfde3a97784f58`

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
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `f3e3277f573e68d8808c36b7465a076808f17ef68f079a6572357bd5dc6d28bc`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `57f83deaa2baae8b7d439147b140ddd424988abb3f1128de2d29cc72ce6b1ec3`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_PLAN, INTERLOCK_BLOCKED, BUSY, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `ef88f098f05122d34101c7175082fdf7415ab355f810ce25235d1ea56ac87222`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `77b0bda1e8301c6ae41bd8aea675123bd2b09b50bfa9ff804c3e68221cc4ca0f`

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
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `5aadf2824cda826a0a3bd3376d87ce88ba20818d87a9e8ca8e8f94d20b56eaf7`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `b8fccf97e567becbaa314d11f3a53d753b8429fb4ebab1eeb72e45f7c4c8bcba`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, CONFLICT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `4d6f3ed87280af28b4596055bef52040a66c1b80b739d6962b9909d9b2d78ce5`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_INPUT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `d8b6ed7fa7b95ec8efed606228bb7a889e5c898df0d8186cf3fc8199e12a3c4a`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, CONFLICT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `f33185eae2537485ee50848067c53f0252410367141bb0bfdd6b7d640a738f49`

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
- Maximum duration: `60s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_INPUT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `2c1138b4e5999015a383f2be19cfd4e42c67ce5df5b9035ee85ef07127191cb3`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_INPUT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `3c8eded61a1c554817e73d319bdd8b15ea673b0ad914643aed072010bf0c2b6a`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_INPUT, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `e7b21b965185a994702d48ac05c505b8c494ca9e53d35ec8922ebec5103e8ecc`

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
- Maximum duration: `5s`
- Canonical CLI template: `robotctl adapt evidence resolve {reference} --robot {robot_id}`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `f5b4b63d2916476ffc5d209d03361abeb3ce612ad4bfc95e6f07646d3c7ace8b`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `1efa1762cafd9ba880523d48fa84a9eae4127351b6a6298af48ce6df5e0fcae6`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `d3184f9e1292c4836224bedd653213c9a17213fbb81a9b1deff9272fc4a4a0e0`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `97bdbc322c026889f60df4dfbf659c26d8ce9f44b4a6a71682c901bfb03776aa`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `6cfa28e62ac93b1b7b4ff1bbe3cfb41b1d83c71a0068d090c08433855f6d0b9e`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `1fe88a6aa8f0859a72640d3ec284c1b8cde2f501a84b9a558f97e377df27d2b3`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `a231e8cfc4b90a17b7e3e4a73a5afbdff3649e76ef31b74dd6a17a41dea38892`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `6a614d58d6baa8c10e731cd5441145364e4a7b5af152fba294ebdd34bb05c2bd`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `26f4a674ad138e46c8e5fd8376b9c13ea9fb51469a00d125ba7d494eb998d237`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `7ebfc89e5cd8e56a1d1ca998f4c12f7ccc3ea897951838ec189636532c814893`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `a493693c3d1ad87b5d165e34c0d12415ee7da273c4a4172368ffb20f5b4d2c6f`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `4346905c6696982f50764cd9ea8cd45bc45a957f5e9323734c1efdd577ace3a9`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `2a952cb5a6b38768069b0d281671ca6a2d6c0223cc74706f38b7141afe8484ed`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `8a976f41bbc69b8fb369a0268693c8f4ef1fb085d2f97086a51f6f85b562fa04`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `0877492877c7fcfa18973edd0e2167c9ef4b132feb9de30e49bd973d367bbb41`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `5888127c286e74a38d9a842c0360929156caa98cfab1088ea2aaa141c6852e91`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl hw inventory scan`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `aa48f8f709e450a4be1a37285dcfb1a719275705c9601700c9054381383cc9d0`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `a7cf734e909878542beb861526cef20bdc37e13ae2fb20f43b6dbb39d8cadfb9`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `194c7e6d95a9c457d609ef49c20a65ddf3569bd40beaac0eca64e00a94556e27`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `9a5a367f19a3353937a1b45d9127202726077b3fee82c0ea46f1600cebc1a1ff`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `13b6e924a426e22342f4bea0394910aec55e6c75b0448034c30e608df26cddc0`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `d6897bc5b7a89cbee258141dfc9b8db4f85fec75a42ac9f335177dad1d4c4dfd`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `5d772f8c1d6bff7f2e29ba712a7c2863c5164422aca2f3a50f1c018c65fccd4c`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `bb5395ddde0cce4600ad930b9b36f0489bef7fff60a0f10ca3e540f087d49ce5`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `8d3596aa75239d7875f1ced5baf5d72ca7156911f44a73f65516479588837dce`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `7a1a644898d6b5d742ebfc4ac5cf618bf5c861e19da9b2c923be5e7bcb42e72e`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, INVALID_INPUT, OPERATION_FAILED`
- Contract SHA-256: `969c689c8d7383a57e493199af6f02a9cd8d714c53b32b1b6194ed00e1564e66`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux binary describe {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `e8d7925c3c08f14f4c246891ef8175a84a87f85ef04aca7efefd95086d2a69f8`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux binary verify {path} --expected-sha256 {expected_sha256}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `4390b04b802c4fcd9a7fea41fa5e894c24a9271b4e36ae802353adb8a3d5db9e`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux cli probe {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `cd0ae504fed4b20d8b3e4e7c0d9274be90bd02946a970579000752242398b81c`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_ARTIFACT, DIGEST_MISMATCH, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `7d6b627204c0ce6e4b35c3e78f2f89d8e4881afdd716e868d2079c960627a79f`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `baeead7f2112ff79e1787b97455e113c0fcf6ac1f8c58d76c25bf70e639c1415`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `f650ac7536b2ac2632a99a14d3832624c5ae1907250fed06005b6b6ee18ab82e`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux config locate`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `9c723f3143a60547ebf395bcf8241cd0a9982f051e1ce74baac7be5c9366f71a`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_ROLLBACK_TOKEN, TOKEN_EXPIRED, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `bb609ca4ae4dac380e5abfb9a8218842960b06681d9f639a08ef9c6a709d29a3`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `9f81c9d8a4c095e684dff08bf1e0294adf0517d1365273d79a49c36d0f1c6cc5`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux container inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `9791e58c012c96ef5e44513800b0a608b5e8ec2192f87fff7e14e7a3724307e0`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux container list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `0275ea0eb987022c7d448ebb4f42754f75d1132926eb4665e99780ab970d3a8a`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `b609694b91002ccbf1a3109edc8e0d0af4739076269a56f95af17ee416af0f8f`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `d20ba9a0cdf610a7b5df1ead47840a70236d564be9db5d55cc6bad7f1d059033`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `d37fa16af97d1006a5065552e2e4bd4137008a17d7db6c40a0c2d05fd0da01d2`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux container stats`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `c3134dcda1b9a44949c0a20ecbf6f953691ab52f91477ea2225f890f1a80687f`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `78baee45010be3df6dd8d4741b275ee0fc5eecb7c8d0ecb3dd62fcf2b21ea833`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux file hash {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `1db2450e5dd43d55064f66360715dfcd0b9683dc1af7fffca570cce2704cedbc`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux file inspect {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `2a9012809d63f0c71810af77b9adcd7653b193b27c981d622b537c5c1a0098de`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux file list {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `6eba479056df742114232594809092b5df949b69a9dd06df65480c1e27757ea8`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `0683ab04070244d590ea63ad20dfbdbc164dc0053f0de58c8d8eaa59f5bdc858`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux host inventory`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `6c021bfe8274369e46bc07498c16148156759f4b7b9e1182c675b9debaf5222c`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `45a0f4aeceffbb62737829ce4a1cc42a6f5d7b905dfcbdc34db4225c218a6549`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `1a4825f74953feed48a341b0cd5de0a7863d316041c809f70a78dd08663da1d7`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux host status`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `b020964455d9cb5f4f65dbc42ee62710fd5b1bc01cf05c2c61c8a064a63ab3fa`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux host uptime`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `b867ba35d98c14519275e9b1f05da6aaa4a5968b0c137083e3c03fc2115b03f7`

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
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `5ec70ab86f56f946bde25f825974c9b2b1556b88218008509c9239c3093be167`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `4a6ccd345a9019e482acf49dbed6a73bfcdf10d1fd467ee07a27448b3f84afd6`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network connections`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `afe1ca7a80366ccc8c047a48be49004ca4e069b0598186bd88388abef427d5ff`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network dns`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `075d95f7b90d757fe3069e68851a3c45a8e8beea731c8f49f55780b293a088ad`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network interfaces`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `77dd7b3b1e7b92d5f7adb7aff6f859b3299dba7cf367b6fde0e8122ac72aa437`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network listeners`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `51dddcaf664e9f13953f7bc8523957c92ee2579b09a797640a620e29c25c98a7`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network routes`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `625a055fbe0539bb1704970f9af5e3b23b8823bcf07eb9fed7c392e0df467ab0`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux network statistics`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `ee37dedef093e310b6af329403617db108a01993d0c6e39e0ed8d807c3547a19`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux package inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `902d0218061f8278f11b9a2ed85fb554c23c971de858ea0b3cd8f076685b849a`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux package verify {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `1e91c0383fc1360ba403805901387e2e8412aa7acb17f2387128c0cfa997cebb`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux process inspect {pid}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `f8257b90f31260968f8e6339bdf4acb212d90345f2578eace59a4691ee174ac3`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux process list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `9354dc23fdcc434e0b604788da24892d2edd48b6b87236e3184f4dca6830878b`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `759b92570e3db9cb7f874de33c95ef40e262c18021e8e64b02948520cfc81fbf`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux process resources {pid}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `aaf3385d55891c045157af619a8fc337793b4dceea523ae6d7f728374ec5fd3a`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `b0c4efdc9accfea7340d6bcc4b4508c92edf10af02e7ab9ad1f4172bccb1522e`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `ef365b5526d3ddc5b50d299b88e5f75bd08de7cc1bd7f9bd158627cb9e7e1fdb`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `2f97a8a1f7afe45ec1c180f6c43fed52cbf8462186d979796ff0fcfae0f14764`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `481f194980dcc0b2ef23eb5088035a2cdf2d23cfc78f2eeb76143ff519769e2c`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux resource cpu`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `5d8e7681d4c1d8518f9482af83591fe6cb94f41a98fae159def0b5aa3dcc5631`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux resource disk`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `805a2e7b9bd4f2f7ef2d6818683ed033cf252f19b8f14e81eff2f5a27cef49c4`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux resource gpu`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `fbb0f2bb82b30a133f86c41c6fc219d778eb6ee4a1a7f4148fcde97b41010615`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux resource memory`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `527924269ed98f4ee8a5a3e6fa9e90f70c4ba12b5e03c5c56a7d7632f57e1cd3`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux resource snapshot`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `fb5db5d0e3d387cbaae79bf93cab5192f5f7410764e6bfb39edb99ea480ca760`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `19ae1543002b31b18843e9ec009e9b4823e7d1e22411f1b1f7a70741219d22d1`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `af4b58116a9d4ae86e0cfeb3d6a032bdc07204208b4516df615faf66672b950c`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux schedule inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `f4d4da5ab90f6a2866048f84d8aaabab829da6ac496aaa7fefd3e48d1783f45b`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux schedule list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `70b691637bf47e4918bbeb6249b4766dcdfecca8b36865b4de7c98636452b9d0`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `7bc25e845864d1cc400bb0d2fb2b7779ef41da8cf85d1fddaa8dcb93422bd8d3`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `8460f0929f3c0f5d91ab41fba437329ed93c343c0f1505c6e48015dd67c7a03f`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `29f5206cae4c8ee28c2f6c2628d41a9e9fad66ac5f9f99420a7dcf03653cbbf3`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux service inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `22f003f4e61d1d9d72be3b172c0cb0748e7151d1250ec3e57b2a0a5db6545edf`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux service list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `a53b458d1945e7b60bb50846304a95da2ef5b3b11bc46ee50e1f56c0acccf829`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `1732536829c06c4d2793d3453be94dbcec8b487d1f52c7b490aaeb9ef27fe9f9`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `aae230addf632fbe4efa1b53a1e8981a12cb4ee3b3422117f32afb073ef589c0`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `b9d118a922036ab6d87f0edfcc9bc6106d04d6142707d8cfa04cee690d16f2ca`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `d4743a3ee4caadc2b6c141cef8076b6d5e92572f83283761cc5c36e7378bb915`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl linux time status`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `871fff04d672c097a7b0d44376057686d488e0c616693e4f2be4e092859d8c63`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, PRECONDITION_FAILED, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `bfc2b579198caea08a292ce391f8a85635dbb62432ae7e4e1fcd24284e36ae0b`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl middleware graph snapshot`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `88957bf5cd1e2089e0476fd1da19b9cd9ddbec8b75ec70e1ee65192bac44af58`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl middleware inspect`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `438145c10f91d9c40d41eafc40cc7a16cdf9fdb119b23705e6d0e1de537e4842`

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
- Maximum duration: `10s`
- Canonical CLI template: `robotctl middleware status`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `d5608bb6d4ad3af5b09ac009e3bd03e6af5332fd31e842b5e114d2ce0ee00a2b`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros action describe {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `3dc0728ff5d0e82f50600164be423b4ecf1d382ca965a14edbb6b7c3360190c0`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros action list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `cc8150b3f4e3ae191409a1e3a52072ca8373fd80dceeed468c1f627fbeaa87f9`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `856b71ddc791585a13d977733c32192205f240443b0e21b604baead19ad7e4e9`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros bag inspect {path}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `337b30b8869d6e0465739296ba15055b04adf74349a3fb58a8fd6d5683e9231e`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros clock status`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `6695485c7542f2fe47c482d8464127fd46b6541b521c529ef428f0a31f44c890`

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
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `6122394914a6359a1fc9751050d70571779da37027013d1d6b8c5e4af04f29bc`

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
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `6546b19435363b1b8eeb24a61521ec44b2bc09bda26d28e3fab3814675c18555`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros graph snapshot`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `cf294e45e10b3e67ac94b2797bb2b654af2205523b12bd120beb42c9cea31607`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_TRANSITION, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `f443c219e5f7bd95e904107990a6ddc75919fc94932d1f1d48c9e4760131fa6c`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, NOT_AUTHORIZED, INVALID_TARGET, INVALID_TRANSITION, TIMEOUT, OPERATION_FAILED`
- Contract SHA-256: `fc20b82c716c1dfdeebb1d34888590eb03b803ba1e79298bbf2b3a3dae02fa20`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros node inspect {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `d7e5ca70c23e291adc2c27439626d8ea240555885169d8158207aeb828c83f55`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros node lifecycle {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `96f7f7c31d76f89afb5586d2995e62516449521bbbe27e8e6e6185abce7554ef`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros node list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `044c490223a88be3e4010772da8a03617a13a9ab999680ad8de0e0623af2f4ad`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros node status {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `e71215c8b152b67dca0814acaa27bd4edc36f48d7e481115e7e723587afb5b21`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros parameter describe {name} --node {node}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `1d7d9311c7426e9457822cf933582872ac99fc63e39715ba2d02f319599d7868`

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
- Maximum duration: `30s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `1ebe9c8db1467a30d7e6618ce94536fabde340e7daed37bdbe1830c2b4dbcef3`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros parameter get {name} --node {node}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `84bd87e5bb0115441c4a0764004e63d3d13a5c85a08a09137c43ba83872489ac`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros parameter list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `69b0abbfa962c9f5c002ee7e81d5b0d5e41c6e4d2022cff5cd1231dd1e886563`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros service describe {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `d62882012d854fda44c22ff8b9d6dccaff181d8a9d84d1fbbf7be74c86928635`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros service list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `f10a08655f32d32b5e616d5c992ebd700a0a16d27944ebc77b8e7c7705d9b71a`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `1cf7f81868495e3030882ca480b64a10a294081d8cc6eddebf9bf488736abf9c`

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
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `428c33833e90b78c4495a45aa1a64b5aa6bd6dc70bb7dc0b13f2fde3f027ea96`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `6bca07a18125d75f37eb4ab7e91b9ee1005f8cf53b52a034a35b757230e9218a`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `4d4dc1844b0bcb51687ec4b427e6adc00b45e479310cce811e655e9532bd916a`

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
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `faa27a7da100f8833814b4cfc1d2a8370fdae92a75794a9610b73099eb7aa6a9`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros topic describe {name}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `b4e8f60ca6b9add7e4e95c52aa9036f259ed598300dbaf299fb33d61b3e4c53e`

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
- Maximum duration: `15s`
- Canonical CLI template: `robotctl ros topic list`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `715b718dfcc2bfb8e9b72ed118b9be588d6ad5333e80d0ce2322ce011755fb09`

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
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `88a926ba59a2a8b24cc5524bbb189b3f1834956c05bb7f99b5f632a8b53e0e21`

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
- Maximum duration: `35s`
- Canonical CLI template: `robotctl tool invoke {operation} --robot {robot_id} --input {input_json}`
- Error codes: `UNAVAILABLE, TIMEOUT, PROBE_FAILED`
- Contract SHA-256: `7e7949f309d5de96ac4ac0eac39a7fb5f2a08667b5e70db6a48d8fcf7a38961d`

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
- Maximum duration: `5s`
- Canonical CLI template: `robotctl runtime health`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `f334aa1fb19fd393b5656ec6439c24d8f2086f32e71e76a8f8dead8318448163`

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
- Maximum duration: `5s`
- Canonical CLI template: `robotctl runtime version`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `bc7070c95666b06970525b83c3ba15a2b1f8f8ac452e0a229dc6919758d2e96d`

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
- Maximum duration: `5s`
- Canonical CLI template: `robotctl state graph query {query} --robot {robot_id}`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `213faf9ea18a1accd2bef6b49c48c0f0d39a852fcb018c6b3377f22e7f552f5e`

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
- Maximum duration: `5s`
- Canonical CLI template: `robotctl state graph snapshot --robot {robot_id}`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `561dd662b9f7a272ea3375f9bb347788311a940b350c9b8d910cd832d62a3329`

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
- Maximum duration: `5s`
- Canonical CLI template: `robotctl tool catalog --robot {robot_id}`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `d46b5cccb0b1697b519eb154993a10add63dc11c739037b1f3eeb5b4bc318e0f`

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
- Maximum duration: `5s`
- Canonical CLI template: `robotctl tool schema {operation} --robot {robot_id}`
- Error codes: `UNAVAILABLE, TIMEOUT, CONTRACT_MISMATCH`
- Contract SHA-256: `76d041c3ca220820a2e65dc55557b638c4cb4b5b9c9a8165fb30ccde214c0055`

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
