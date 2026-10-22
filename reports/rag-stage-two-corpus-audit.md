# RAG Stage 2 Corpus Quality Audit

生成日期：2026-10-19。算法：`pdf-chunks-v2`。
配置：`{'max_chars': 1200, 'min_chars': 300}`；阈值：`{'very_short_chars': 100, 'many_chunks_per_page': 10, 'example_limit': 100}`。

成功处理 13 份 PDF，共 2178 页、4547 个 Chunk、3771505 字符。统计保留短 Chunk；告警和候选污染不等于已确认错误。

## 每篇文档

| 文档 ID | 页数 | Chunk | 字符 | 空 Chunk 页 |
|---|---:|---:|---:|---:|
| epics-application-developers-guide-r3-16-2 | 354 | 848 | 741481 | 0 |
| epics-documentation-latest-2026-08-18 | 455 | 1074 | 927666 | 2 |
| european-xfel-full-technical-design-report-2007 | 646 | 1730 | 1469173 | 5 |
| european-xfel-undulator-commissioning-spectrometer-cdr-2011 | 21 | 41 | 32036 | 0 |
| european-xfel-x-ray-optics-beam-transport-tdr-2012 | 164 | 235 | 169328 | 0 |
| european-xfel-standard-e-beam-diagnostics-linac2010 | 3 | 13 | 12438 | 0 |
| shine-epics-ioc-pv-information-management-pcapac2022 | 3 | 13 | 11677 | 0 |
| shine-accelerator-fast-interlock-2024 | 9 | 18 | 15651 | 0 |
| shine-control-system-status-icalepcs2019 | 4 | 15 | 13895 | 0 |
| shine-cryogenic-control-system-2021 | 8 | 22 | 18792 | 0 |
| shine-white-rabbit-beam-synchronous-timing-ipac2022 | 5 | 17 | 15196 | 0 |
| shine-accelerator-control-system-design-presentation | 34 | 34 | 5965 | 0 |
| shine-accelerator-preliminary-design-report-2017 | 472 | 487 | 338207 | 1 |

## 长度与页面分布

| 统计量 | Chunk 字符数 | 每页 Chunk 数（含 0） |
|---|---:|---:|
| min | 1 | 0 |
| p10 | 387.20000000000005 | 1.0 |
| p25 | 611.0 | 1.0 |
| median | 899.0 | 2.0 |
| p75 | 1078.0 | 3.0 |
| p90 | 1163.0 | 4.0 |
| p95 | 1184.0 | 4.0 |
| max | 1200 | 6 |
| mean | 829.4490873103144 | 2.0876951331496785 |

极短 Chunk：52；超长 Chunk：0。
无 Chunk 页面：8；超过每页数量阈值的页面：0。

## Parser 告警分布

| 文档 ID | 空文本 | 疑似扫描 | 双栏 | 乱码 | 私用字符 |
|---|---:|---:|---:|---:|---:|
| epics-application-developers-guide-r3-16-2 | 0 | 0 | 0 | 0 | 0 |
| epics-documentation-latest-2026-08-18 | 1 | 0 | 0 | 0 | 0 |
| european-xfel-full-technical-design-report-2007 | 5 | 0 | 0 | 4 | 0 |
| european-xfel-undulator-commissioning-spectrometer-cdr-2011 | 0 | 0 | 0 | 0 | 0 |
| european-xfel-x-ray-optics-beam-transport-tdr-2012 | 0 | 0 | 0 | 0 | 11 |
| european-xfel-standard-e-beam-diagnostics-linac2010 | 0 | 0 | 3 | 0 | 0 |
| shine-epics-ioc-pv-information-management-pcapac2022 | 0 | 0 | 3 | 0 | 0 |
| shine-accelerator-fast-interlock-2024 | 0 | 0 | 4 | 0 | 0 |
| shine-control-system-status-icalepcs2019 | 0 | 0 | 3 | 0 | 0 |
| shine-cryogenic-control-system-2021 | 0 | 0 | 0 | 0 | 0 |
| shine-white-rabbit-beam-synchronous-timing-ipac2022 | 0 | 0 | 5 | 0 | 0 |
| shine-accelerator-control-system-design-presentation | 0 | 2 | 0 | 0 | 30 |
| shine-accelerator-preliminary-design-report-2017 | 1 | 0 | 0 | 39 | 23 |
| 全部 | 7 | 2 | 18 | 43 | 64 |

## 清洗后候选问题

| 类型 | 次数 | 主要来源（次数） |
|---|---:|---|
| replacement | 1017 | shine-accelerator-preliminary-design-report-2017: 1017 |
| null | 4 | european-xfel-full-technical-design-report-2007: 4 |
| private_use | 299 | shine-accelerator-control-system-design-presentation: 170; shine-accelerator-preliminary-design-report-2017: 65; european-xfel-x-ray-optics-beam-transport-tdr-2012: 64 |
| publication_identifiers | 2 | european-xfel-full-technical-design-report-2007: 2 |
| copyright_license | 21 | epics-documentation-latest-2026-08-18: 13; shine-cryogenic-control-system-2021: 7; european-xfel-undulator-commissioning-spectrometer-cdr-2011: 1 |
| isolated_page_numbers | 588 | shine-accelerator-preliminary-design-report-2017: 540; european-xfel-full-technical-design-report-2007: 14; shine-accelerator-fast-interlock-2024: 12 |
| running_publication_codes | 19 | shine-accelerator-preliminary-design-report-2017: 13; european-xfel-x-ray-optics-beam-transport-tdr-2012: 5; epics-documentation-latest-2026-08-18: 1 |
| suspicious_hyphenation | 634 | european-xfel-full-technical-design-report-2007: 389; epics-documentation-latest-2026-08-18: 120; epics-application-developers-guide-r3-16-2: 36 |

内部连字符仅在 corpus 中存在无连字符拼写时列为候选；可能包含真实复合词。出版编号、版权词和独立数字也可能出现在有效正文中。审计不修改文本。

## 三类重点文档

### The European X-Ray Free-Electron Laser Technical Design Report

646 页、1730 个 Chunk；无 Chunk 页面 5。
告警：`{'empty_text': 5, 'possible_garbled_text': 4}`。清洗后质量信号：`{'replacement': 0, 'null': 4, 'private_use': 0, 'publication_identifiers': 2, 'copyright_license': 0, 'isolated_page_numbers': 14, 'running_publication_codes': 0, 'suspicious_hyphenation': 389}`。
Chunk 长度：`{'count': 1730, 'min': 54, 'max': 1200, 'mean': 849.2329479768786, 'p10': 453.0, 'p25': 660.0, 'median': 902.0, 'p75': 1067.75, 'p90': 1158.0, 'p95': 1183.0, 'very_short_chunks': 1, 'very_long_chunks': 0}`。

### 硬 X 射线自由电子激光装置初步设计报告（加速器分册）

472 页、487 个 Chunk；无 Chunk 页面 1。
告警：`{'empty_text': 1, 'private_use_characters': 23, 'possible_garbled_text': 39}`。清洗后质量信号：`{'replacement': 1017, 'null': 0, 'private_use': 65, 'publication_identifiers': 0, 'copyright_license': 0, 'isolated_page_numbers': 540, 'running_publication_codes': 13, 'suspicious_hyphenation': 4}`。
Chunk 长度：`{'count': 487, 'min': 29, 'max': 1200, 'mean': 694.47022587269, 'p10': 396.6, 'p25': 532.5, 'median': 684.0, 'p75': 876.5, 'p90': 1016.2, 'p95': 1095.1999999999998, 'very_short_chunks': 11, 'very_long_chunks': 0}`。

### SHINE 加速器控制系统设计与开发

34 页、34 个 Chunk；无 Chunk 页面 0。
告警：`{'private_use_characters': 30, 'possible_scanned_page': 2}`。清洗后质量信号：`{'replacement': 0, 'null': 0, 'private_use': 170, 'publication_identifiers': 0, 'copyright_license': 0, 'isolated_page_numbers': 0, 'running_publication_codes': 0, 'suspicious_hyphenation': 0}`。
Chunk 长度：`{'count': 34, 'min': 3, 'max': 388, 'mean': 175.44117647058823, 'p10': 68.0, 'p25': 123.0, 'median': 159.5, 'p75': 226.0, 'p90': 294.7, 'p95': 307.4, 'very_short_chunks': 8, 'very_long_chunks': 0}`。

## 高优先级异常样本

以下样本优先展示乱码、NULL 和私用字符，其次为版权词与断词候选。示例经过截取，精确位置与完整页面统计见同名 JSON。

1. **replacement**，次数 166，`shine-accelerator-preliminary-design-report-2017`，物理页 308～308，Chunk `shine-accelerator-preliminary-design-report-2017:eb2593d24b917ae17f32682933c7bea2cb9f3317523ee0f0cedf0c1e30b2c782`。

> 设计报告——加速器分册  304  图3.3.6.1-30 束流倾角入射示意图  对整个腔体长度进行积分，得到束流倾角入射时在腔体内激发的信号如下所  示：  ��= A  −�  2  � 2 ����� න �−  �+ � �����  2� �����+ � �����  ��  �  =  �����  � �−  �  2� −�  2  � 2 � ׬ �−  � �����  2� ��������  ��  �����+ ��������  ��  ����� dz  当条件2\uf070 \uf074 \uf077\uf03c\uf03c 时，即腔体谐振信号周期远小于衰减时间常数时，积分项内当z  从-L/2 到L/2，�  �  −�����  2�项结果均近似为1，因此可简化成：  ��≈  �����  � �−  �  2� −�  2  � 2 � ׬ ��������

2. **replacement**，次数 151，`shine-accelerator-preliminary-design-report-2017`，物理页 310～310，Chunk `shine-accelerator-preliminary-design-report-2017:f75c40caa286bba7a25644a8ddfcf12a0ae542009fa07a0ebe8d0246b754d4bf`。

> 硬X 射线自由电子激光装置初步设计报告——加速器分册  306  ��= A �−������−�  2�������� �  图3.3.6.1-33 束流倾角入射示意图  对整个腔体长度L 进行积分，得到：  ��= A  −�  2  � 2 ����� න �−  �+ � �����  2� �����+ � �����  ��  �  = �����  � �−�  2������ 2�2���2� �2 ��� �� 2�����−������ � ��� �� 2�����  −�����  �  2����� � ��� �� 2������−� 2������  从公式中可知此种情况下分解成了两部分，第一部分和公式（7）相同，等  效成束流

3. **replacement**，次数 115，`shine-accelerator-preliminary-design-report-2017`，物理页 312～312，Chunk `shine-accelerator-preliminary-design-report-2017:d8b3d052a0ed5620d89f63eefdcf1d5a35c4212ed6a9f98875622f7af267040c`。

>   设束团长度为 z \uf073，束团电荷量为q ，束团自身倾角为\uf061，等效结果可视为  将束团分割成一组组带电量为dq 的电子沿z 轴分布，则每组电子的位置偏移量  为�tan �假设束团呈高斯分布，则有：  ��= q  2π�� �  −�2  2��2��  结合此前公式，则有：  ���= ω  2 � ����  ( �  �)0�  −�2��2  �2 �tan (�)  �0  �−�  2�sin ωt ��  = �tan (�)  2��� ��  −�2  2��2�−� 2�sin ωt ��  积分得：  ��= �tan (�)  2��� −∞  +∞  ��  −�2  2��2�− �−�  � 2� sin ω �−�  � �� න  = �tan (�)  2��� �−�  2�  −��  +��  ��  −�

4. **replacement**，次数 47，`shine-accelerator-preliminary-design-report-2017`，物理页 325～325，Chunk `shine-accelerator-preliminary-design-report-2017:4157c937fdf3da15ac24a6fb0c28e0c755018176982fe7cc1bbe6408ce75e7ca`。

> 用重火石玻璃（SF-11）  作为光学展宽器。激光通过重火石玻璃，由于群速度色散（GVD 效应），出射激  光脉冲宽度将会展宽，展宽宽度与介质厚度的关系为：  ��= �0 1 + 2��2 ��  ���2  �0  2  其中：T0 为原始激光脉宽。通过选择合适的介质厚度，可以得到所需的激光  脉冲宽度。  （2）电光调制  考虑到激光与库伦电场在晶体中的速度不匹配、晶体对库伦电场的衰减及晶  体表面的反射折射影响，可得晶体的响应函数为：  ��= 2 1 + ��+ ��(�) 1 �  0  �  −∞  +∞  ����2���  � ���−��� ���−2���(�)�/����� න න  对应不同厚度的GaP 晶体的响应函数曲线，当选择晶体厚度在0.1mm  以内时，将得到较平坦的响应曲线，如图3.3.6.1-44 所示[7]。考

5. **replacement**，次数 46，`shine-accelerator-preliminary-design-report-2017`，物理页 307～307，Chunk `shine-accelerator-preliminary-design-report-2017:a03866d947e776cd8fe7944f14d0a9b501e9bfa53b4d6a28af65c4718e35d2f6`。

> z 的  小谐振腔，则腔体中激励信号即是一个个小谐振腔激励信号的积分的结果。  当束流沿平行中心轴偏离电中心距离为x入射时，腔体激励信号电压由公式  所示：  ��= ωqx  2x0  Z �  � �0  �  −�2��2  �2 �−�  2�sin ��  其中 0 [ ] R Q 是当束流偏离腔体电中心x 时的分流阻抗，假设此过程中束团长  度条件不变，腔体参数也固定，可将常数项分离，令：  �= ωq  2x0  Z �  � �0  �  −�2��2  �2  则有：  ��= ���−�  2�sin ��  当束流按一定的倾角θ经过腔体中心时，其模型可如图3.3.6.1-30 所示，则腔  长为dz 的小腔体的激励电压为：  ��= ��tan ��−�  2�sin ���� �

6. **replacement**，次数 46，`shine-accelerator-preliminary-design-report-2017`，物理页 83～83，Chunk `shine-accelerator-preliminary-design-report-2017:a4225703095d9aad8881a362bf8d2b288b3c34f6406327cafb9ec0fbce1f132c`。

> 步设计报告——加速器分册  79  位置的剩余磁场要小于0.5μT，即5 mG，式中R0=3.6 nΩ/μT，R1=0.75×10-2  nΩ/μT/mT。  ����= ��+ ��������  超导腔的最佳耦合度与束流强度相关，一般设计使建立腔压所需的功率最小。  当加速梯度Eacc=16MV/m、Q0=2.7×1010，峰值麦克风效应引起的频率失谐为δf=10  Hz 时，利用下式可以求出最佳耦合度βopt=656，进而得到此时耦合器的外部品质  因数为Qe=4.12×107。  ����= [ �+ ����(�/�)  ��  �  + �����  ��  �  ]�/�  ��= ��/����  （2）3.9GHz 超导腔  SCLF 将安装16 支3.9GHz 超导腔，在2K 工作下，加速梯度14MV/m、  Q0=2.0×109

7. **replacement**，次数 33，`shine-accelerator-preliminary-design-report-2017`，物理页 324～324，Chunk `shine-accelerator-preliminary-design-report-2017:5a9eee2ae1958836aa81c41d12340a6d21837198ee5acc0c03077b2ae73507eb`。

> 的是，在束团长度100fs 或更短时，由于  Chirp 调制引入的边带，导致在频域的反卷积过程中得到束团的长度信息时引入  过大噪音，在原理上存在分辨率极限Δ�= 2.6 �0��，其中T0,Tc 分别表示激光展  宽前后的脉冲宽度。  FELIX 在此基础上发展了一不依赖于探测激光稳定性，同时可克服边带影响  的时域解码方法，并可直接得到束团的时域长度，基本结构如图3.3.6.1-43所示[4,5]。  图3.3.6.1-43 单次通过时域解码束长测量系统  从探测激光出来的激光被分成两束，其中一束类似频谱解码法（EO 光），通  过光学展宽器、起偏器、电光晶体、偏振片、最后到达BBO 晶体；另一束（gate  光）通过与EO 光相同的光程到达BBO 晶体，光路上安装一可调光路延时线用  于精确调节光程使两束光同时到达BBO 晶体。两束光以特定夹

8. **replacement**，次数 29，`shine-accelerator-preliminary-design-report-2017`，物理页 331～331，Chunk `shine-accelerator-preliminary-design-report-2017:e1da9c0f9ab1afeb6f0091e19a975b2e3dc158b4d158fbeaf949281f8b3a7ebc`。

>  腔式探头结构  （1）设计指标与技术参数  对于BAM 测量，腔体引出的信号通过RF 前端进行IQ 解调，量化后得到相  对于参考信号的到达时间信号如下：  ��=  arctg ����  ���� 2��010  考虑到测量噪音，最好通过适当的延迟参考信号到达BAM 探头的时间，使  得测量时信号的实部接近0，虚部最大，此时BAM 测量系统的时间分辨率如下：  Δ�= 1 2��0 × ���+ �  2��0 × �� 2 + ������  上式中，第一项来自于测试信号的信噪比对测量结果的干扰；第二项来自于  有限测量时长对频率测量精度的影响；第三项来自于参考信号到达BAM 探头的  时间抖动，基于激光的飞秒同步系统可以提供jitter 小于20fs 的参考信号。虽然  来自腔体的信号在1nC 电荷量情况下高达120dB，但考虑到量化噪音及

9. **replacement**，次数 26，`shine-accelerator-preliminary-design-report-2017`，物理页 328～328，Chunk `shine-accelerator-preliminary-design-report-2017:4f7315b4c733d2a90198150a55eb98b4c9d6a04b21b2b187019ce738379567ac`。

> 一定波长情况下，具有相干性，为  相干叠加。不同距离电子的同步辐射的相干性，随着距离的增加，或者辐射波长  的减小，而逐步减少。故最终同步辐射的总功率，为：  �(�) = �0(�) �+ �(�−1)�(�)  �(�) =  −∞  +∞  �(�)����2�  �������� න  2  其中，q(z)为束团的纵向归一化分布函数，N 为束团粒子数；P0(λ)为单粒  子通过该弯转处在波长λ的辐射功率。在一定带宽内及知道束团能量的情况下，  若能同时测得辐射的总功率，以及束团电荷量，便能求得束长函数q(z)。  系统的基本结构如图3.3.6.1-46 所示：

10. **replacement**，次数 26，`shine-accelerator-preliminary-design-report-2017`，物理页 252～252，Chunk `shine-accelerator-preliminary-design-report-2017:bd8722cbc9f9f617a595703435118c347cb8616533d126ccb337c7345a206ec6`。

> -seeding 光栅单色器采用环面的变线  距光栅，环面光栅使得光栅单色器子午聚焦在狭缝处，弧矢方向聚焦在第二级波  荡器的入口处，根据环面镜的聚焦公式:  ��=  2  �����（  ��� �+��）,��= 2�����  ��� �+��  可以得到光栅子午和弧矢方向的半径，同时光栅采用的是变线间距的光栅，  采用变线距光栅有很多好处，可以总结为：  可以简化光路，减少一些不必要的光学元件；  相比于平面光栅，变线距光栅可以提高光学的传输效率；  变线距光栅可以消除光学像差，提高成像质量；

11. **replacement**，次数 25，`shine-accelerator-preliminary-design-report-2017`，物理页 326～326，Chunk `shine-accelerator-preliminary-design-report-2017:9323f1bc02be0995c97026cf189d4857685ab34e535b83d74012521e86e723e4`。

> 硬X 射线自由电子激光装置初步设计报告——加速器分册  322  ����(�) = ����[�(�)�(�)]  由晶体的响应函数曲线可知，采样的有效库伦电场幅度约为入射电场幅度的  一半。  （3）BBO 晶体二次谐波产生  对于二次谐波产生，拟选用偏硼酸钡（BBO）晶体。BBO 晶体具有透明区  域大、相位匹配范围大、非线性系数大、损坏阈值高、热吸收带宽大、光学均匀  性好等优点。  图3.3.6.1-45 BBO 晶体二次谐波产生  具体方案拟采用非共线I 型相位匹配（o+o→e）方案，如图3.3.6.1-45 所示：  假设BBO 晶体的主轴与晶体表面法线的夹角为Θ，两入射光对称入射，夹角大  小为2Φ，两入射光均为水平偏振光，出射光为竖直偏振光

12. **replacement**，次数 24，`shine-accelerator-preliminary-design-report-2017`，物理页 82～82，Chunk `shine-accelerator-preliminary-design-report-2017:95ec8cb36704343e4accdce5ec51b9e664341c3de272f5157658adc352e0cfa9`。

> ，与加速腔压Vc 成正比，曲线如图3.3.3.2-3 所示，Eb=8.0GeV，所  以为降低建造和运行成本，亟需提高超导高频腔的无载品质因数降低动态功耗。  ��������= ���  �  �/�× ��  = ���� �/�× ��  图3.3.3.2-3 SCLF 超导直线加速器总低温动态功耗与超导腔品质因数关系  SCLF 计划采用高纯铌材，利用冲压和电子束焊接成型，然后进行电抛光结  合氮掺杂的表面处理和一系列表面处理流程和洁净组装工艺，保证获得高Q 值  的超导铌腔。在制造前必须对所采用优质高纯铌材进行全面检测，从原材料上严  格把关，以保证超导腔的性能，表面有缺陷的铌材则直接淘汰，严禁进入下一个  制造环节。电子束焊接成型的哑铃，需观察焊缝确保无焊接缺陷，同时利用专用  测量设备测量谐振频率和哑铃高度，偏差大的哑铃不能进入整腔的电

13. **replacement**，次数 23，`shine-accelerator-preliminary-design-report-2017`，物理页 196～196，Chunk `shine-accelerator-preliminary-design-report-2017:6d4a01caba64a1d5d709001139d643d5b7780977dd497af2dab239c4919c23be`。

> 硬X 射线自由电子激光装置初步设计报告——加速器分册  192  mcollimation~80�，可得在septum 入口处的束流垂直偏移约为  �= �������+ 2������������εβseptum ≈15��  在此要求的基础上，我们采用总共10 块kicker 磁铁，每五块为一组，分别  放置于两块四极磁铁中间。每块kicker 磁铁的角度为0.1mrad，总偏转角度为  1mrad。由于四极磁铁的磁中心位于直通线上，因此经过kick 后的束流会偏轴经  过四极磁铁，感受到一定的二极场分量，一定程度上改变了实际的偏转角度。经  过模拟研究，在如图3.3.4.2-2 所示的布局条件下，产生的垂直方向轨迹，可以满  足septum 入口束流垂直偏移的要求。  图3.3.4

14. **replacement**，次数 21，`shine-accelerator-preliminary-design-report-2017`，物理页 315～315，Chunk `shine-accelerator-preliminary-design-report-2017:0c9b2e1e0f5438417907f20b457a4a78ee0c8d482d98df9597ec4ac64be1c00b`。

> ′以及和  2 号腔体测出的束团位置U2 进行对比并采用统计学的方法进行位置分辨率的评  估。验收原理可由图3.3.6.1-41 和以下方程表示：  U2 = �12 × �3 + �23 × �1 /�13  δ����= ��× ���Δ�  ��= 1  �23 �13  2 + �12  �13  2 + 1  图3.3.6.1-41 系统性能指标验收评估示意图  6.1.3.3.7 系统研制风险与控制  前期为了SDUV、DCLS、SXFEL 的位置测量进行了CBPM 系统的研发，  积累了丰富的经验。腔体在加工上对频率和Q 值的要求需严格控制，前期已完  成相当多的加工实验工作，腔体设计加工上基本无风险。系统研制过程中着重射  频前端引入噪声大小问题，验收需严格测试以及现场安装需关注电磁屏蔽问题。  6.1.3.4 检测设施  6.1.3

15. **replacement**，次数 19，`shine-accelerator-preliminary-design-report-2017`，物理页 261～261，Chunk `shine-accelerator-preliminary-design-report-2017:2ea2ff53b18cd04033368f85d6bbf0d72dc86279beb9acde25240042d1fcf187`。

> 硬X 射线自由电子激光装置初步设计报告——加速器分册  257  （取n=1）：  �� ����= ��  �  由此可以估算（111）面的单色带宽：光子能量为3.05 keV 时，  ��  �≈ 500�−6  tan 80.75° = 8.1�−5  光子能量为7 keV 时，  ��  �≈ 30�−6  tan 25.47° = 6.3�−5  由两图还可以看出，当光子能量在3keV 左右时C(1,1,1)的透射率较低，故  此时应采用尽量薄的晶体。  图3.3.4.8-11 100μm 厚的C(1,1,1)晶体对3keV（a）和7keV（b）的吸收曲线。  图3.3.4.8-12 50μm 厚的C(1,1,1)晶体对3keV（a）和7keV（b）的吸收曲线。

16. **replacement**，次数 19，`shine-accelerator-preliminary-design-report-2017`，物理页 409～409，Chunk `shine-accelerator-preliminary-design-report-2017:a506d3346a8c2773e34a6ad958fa615f28f0b03ad57a95b7007f0d95703d1252`。

>  使相位关系又回到开始，从而保证能量流动方向不变。我们采用的是熔融法生长  的晶体，对应的包括1550nm 和775nm 在内的Sellmeier 公式为：  ��  2 λ = 2.0993 + 0.922683  1 −0.467695 �2  −0.0138408�2  ��  2 λ = 2012725 + 1.18431  1 −0.0514852 �2  + 0.6603  1 −100.00507 �2  −0.00968956�2  相位匹配是实现和频输出的充分必要条件，而PPKTP 晶体工作于准相位匹  配条件下。在一个相干周期内，两路入射光和和频光的波数之和不为零，即不能  实现相位匹配，因此能量不能够稳定输入到和频光使之实现放大。解决这个问题  的办法是，在相位变化到和频光强度恰好要开始降低时将磁化方向翻转180 度，  使相位

17. **replacement**，次数 18，`shine-accelerator-preliminary-design-report-2017`，物理页 256～256，Chunk `shine-accelerator-preliminary-design-report-2017:03f2efb977d50f586bb64dfeff20b9aaf737818036ed38ed576b1c16ec3b3fbf`。

> g 的光谱宽度可以  达到10-4 以下。  除了能量分辨率，光栅单色器设计还要求单色器要有较高的传输效率。光栅  单色器的衍射效率可以用以下公式进行计算：  �0 = �  4 (1 + 2 1 −����4�ℎ���� � + (1 −�)2)  由此可以得出所设计的光栅单色器的衍射效率为0.0365，当光栅经过某个光学元  件的时候，其反射效率可以用以下公式进行计算:  �= ( �1 −�2  �1 + �2  )2  光栅单色器的反射效率和原子散射因子、入射角、衍射波长有关，若选取金作为  基底，当光子能量为1keV 时，可以得到平面镜的反射效率约为0.9595，从而得  到光栅单色器的整体传输效率约为0.0303。  （3）单色器机械结构设计  根据软线self-seeding 方案中的机械扫描图3.3.4.8-2 可以看出在扫描的过程 

18. **replacement**，次数 17，`shine-accelerator-preliminary-design-report-2017`，物理页 352～352，Chunk `shine-accelerator-preliminary-design-report-2017:2cc12a93eb256ae628f565f8a77faf5a8f6aaae95698a2308e4878848a59091c`。

> 丝，U 方向扫描丝，X 方向扫描丝依次扫过束流，同步采集丝靶位置数据  及丝扫描探头后方的束损探头上的束损信号即可重建出束流截面。  扫描丝的温度公式如下：  �(�) = ��  ��  � 2����⊥  1 ��  dE: 沉积能量  I: 流强  ��: 热容  �⊥: 截面尺寸  �: 冷却因数  碳的熔点为3550℃，热容为0.42cal/g/℃;钨的熔点为3410℃，热容为  0.055cal/g/℃，所以钨和碳是适合的材料。为了防止温度过高导致扫描丝熔断，  扫描速度应该尽量快，需要选用速度快的电机。另外，由于丝扫描探头的RMS  分辨率由扫描丝的直径决定，为D/4，所以扫描丝应该尽可能细，考虑到当前加  工水平以及丝的强度，扫描丝的直径定为4-10μm。丝扫描的位置数据需要和束  损信号精确同步，通过基于事件码的系统实现。每个丝扫描

19. **replacement**，次数 17，`shine-accelerator-preliminary-design-report-2017`，物理页 460～460，Chunk `shine-accelerator-preliminary-design-report-2017:98c9677bb4acc7b0e196dd409188c71b95e3698454b7d8a128d719529d8ae3ab`。

> 在十分钟内，可信  度为95%时的分辨率）。  （3）输出电压纹波  在实际负载下测试，使用示波器在电源输出端进行测量，输出电压纹波的测  试。计算公式为：  ��=  ��−�  ��  这里vp-p为输出电压波动的峰峰值，需要考虑特定的频率下的输出电压纹波，  低频市电整流纹波和高频的电源开关纹波，可以按照示波器直接检测或者通过示  波器的FFT 功能读取特定频率的幅值，作为输出电压波动的幅值。V0 为被测电  流时的电源输出直流电压值。  测量范围：(20~100)% 额定电压。  （4）电流纹波测试  通过电压纹波的幅值和特定频率下的电感的感抗相比较得到电源的电流纹  波，由于不同的负载采用同一电源所以约定按照负载30mL 的电感量来衡量电源  输出电流的纹波值。  输出电流纹波包括：低频（交流电50Hz 的倍频成分）纹波电流和高频（开  关

20. **replacement**，次数 16，`shine-accelerator-preliminary-design-report-2017`，物理页 410～410，Chunk `shine-accelerator-preliminary-design-report-2017:77a9a60e1a83d8f67878c36ba54ae69e997d345e641255a25326a801522a248c`。

> 硬X 射线自由电子激光装置初步设计报告——加速器分册  406  ����= 1 ��(�2)  �2  −��(�1)  �1  −��(�1)  �1  其中，λ为波长，单位μm，λ1 为1.55μm，λ2 为0.775μm，ny，nx 分别为晶体  y 轴和x 轴的折射率，Lyxy 为满足准相位匹配调节需要的晶体的周期长度，单位  为μm。  通过计算得到晶体的周期长度为46.22μm。根据理论分析并考虑成本，选取  晶体的长度为5mm。  （3）光纤稳相控制系统设计方案  锁模光纤激光器输出的参考激光脉冲透过PBS 的部分经过一个四分之一波  片（QWP）和反射镜（DM）返回，重新入射到PBS 时，光的偏振方向刚好旋  转90°，可以由PBS 反射，

21. **null**，次数 1，`european-xfel-full-technical-design-report-2007`，物理页 40～40，Chunk `european-xfel-full-technical-design-report-2007:41864c716e57158efb645448e40349904af7e5566bdba871f2f1e2308fbdead9`。

> n order to achieve the minimum FEL gain length, the optimum beta function βopt ≈\u0000 1 m had to be realised inside the undulator. To this end, permanent-magnet quadrupole fields were superimposed on the periodic undulator field

22. **null**，次数 1，`european-xfel-full-technical-design-report-2007`，物理页 44～44，Chunk `european-xfel-full-technical-design-report-2007:4365aeb693bc7aac8aa5be33e012a8c5a60662e6c16b2ec287b85acd4b5973a1`。

> mately 4 m. This comes sufficiently close to the optimum beta function of βopt ≈\u0000 3 m, calculated for FLASH parameters. Except for this modification, the undulator design remained unchanged.  Progress on the TESLA accelerator R&D has been reported in the “TESLA Reports” series (351 reports so far), while the “TESLA-FEL Reports” series is dedicated to FEL-specific work (109 repo

23. **null**，次数 1，`european-xfel-full-technical-design-report-2007`，物理页 570～570，Chunk `european-xfel-full-technical-design-report-2007:7426db94d1f1821a5002158f6a1a0b099bfc14cfdae0272044c5b53b122fef93`。

> pick up probe (Qext=1×1013). The cavities will be operated in the accelerating π\u0000-mode. The accelerator field will be increased to its maximum value in steps. At each step the cavities will be powered for 20 s in CW-operation mode. In total about 40 hours are needed for one complete test run with four cavities, including the assembly and disassembly of the insert to the cryosta

24. **null**，次数 1，`european-xfel-full-technical-design-report-2007`，物理页 72～72，Chunk `european-xfel-full-technical-design-report-2007:c99ec178ed8ac825af0aff455403db9ab3f0f422a107fcf2112da616c5548efa`。

>  [Ω] 1036 Epeak/Eacc 2.0 Bpeak/Eacc [mT/MV/m] 4.26 Tuning range [kHz] ± 300 Δƒ/Δ\u0000L [kHz/mm] 315 Lorentz-force detuning constant KLor [Hz/(MV/m)2] 1 Qext of input coupler 4.6 × 106  Cavity bandwidth f/Qext [Hz] FWHM 283 Fill time [µs] 780 Number of HOM couplers 2  Table 4.2.1 Parameters of the nine-cell cavity (note: R = V2/P, where P is the dissipated power and V the peak volta

25. **private_use**，次数 30，`shine-accelerator-control-system-design-presentation`，物理页 26～26，Chunk `shine-accelerator-control-system-design-presentation:8b7cf853df55bb7dad3b6f407e4c06639206fc5863e2cc1e91efd8ca0ba7eab7`。

> 运行与开发环境  \uf06e 为整个控制系统提供运行环境  \uf06e 由服务器集群、存储设备、网络设备等组成  \uf06e 采用虚拟服务器和实体服务器相结合的方式  \uf06e 提供各类基础服务，如账号管理、文件管理、时间同步等  \uf071\uf020软件开发管理  \uf073\uf020开发过程记录与控制  \uf073\uf020开发流程优化与简化  \uf071\uf020通道信息管理  \uf073\uf020通道信息采集与存储  \uf073\uf020通道状态监控与管理  \uf071\uf020通道权限管理  \uf073\uf020通道访问权限管理  \uf073\uf020通道访问记录存储与显示  \uf071\uf020网络管理与监测  \uf073\uf020网络地址分配与管理  \uf073\uf020交换机及端口的管理  \uf073\uf020网络传输效率的监测

26. **private_use**，次数 14，`european-xfel-x-ray-optics-beam-transport-tdr-2012`，物理页 153～153，Chunk `european-xfel-x-ray-optics-beam-transport-tdr-2012:7398f7d7eacfd8bc88a27beeca82e25b2f75b899f5b0bbf3ae4305ee98995609`。

> elated documentation  For some of the documents in “EDMS”, a login is required. \uf069  The following documents provide additional technical documentation:  \uf06e “CDR: X-Ray Optics and Beam Transport” (EDMS D*2081421)  \uf06e “UHV Guidelines for X-Ray Beam Transport Systems”  \uf06e “CAD Integration Guidelines for Photon Beamline Components”  \uf06e “Beam transport component list” (EDMS D*2278111)  \uf06e

27. **private_use**，次数 11，`shine-accelerator-control-system-design-presentation`，物理页 15～15，Chunk `shine-accelerator-control-system-design-presentation:ed33970b825e4ae7384f5697ddc3be35844859c890009c20153a864fbeae6729`。

> SHINE 加速器控制系统  \uf06e 设备控制  \uf06e 数据采集  \uf06e 机器联锁  \uf06e 定时系统  \uf06e 控制网络  \uf06e 运行环境  \uf06e 数据存储  \uf06e 用户界面  \uf06e 上层软件  \uf06e 反馈系统  \uf06e 中央控制室  加速器控制系统：  1. 实施对注入器、超导加速  器、束流分配、波荡器系统  中各类设备的全面控制  2. 提供硬X射线自由电子激  光装置调试和运行的平台  3. 满足加速器物理学家、工  程技术人员对设备监控、数  据获取与分析等方面的需求

28. **private_use**，次数 10，`shine-accelerator-control-system-design-presentation`，物理页 17～17，Chunk `shine-accelerator-control-system-design-presentation:dc4aa1528dda7b0dbc098a627e309aaa046775d421a54fa444b6f42bcf572d30`。

> 数据采集  \uf06e 图像采集、波形数据采集是控制系统的组成部分  \uf06e 图像采集：束流测量系统、驱动激光系统、种子激光系统、光学诊断系统等  \uf06e 常规图像采集 (areaDetector)  \uf06cGigE Vision 接口相机  \uf06c图像专用传输网络  \uf06c在线采集、处理、存储  \uf06e 高帧率图像采集  \uf06cCamera Link 接口相机  \uf06c点对点连接方式  \uf06c在线采集、存储；离线处理、分析  SXFEL束流截面测量

29. **private_use**，次数 10，`shine-accelerator-preliminary-design-report-2017`，物理页 190～190，Chunk `shine-accelerator-preliminary-design-report-2017:3c53f500d7e19bf4d008a26e39db97f981c5fd8b4ce83045510ddb9493ac0e53`。

> 个平  衡点。  波荡器磁场整体偏差及气隙控制精度：不同波荡器段之间的磁场整体误差要  求可以根据共振条件确定，不同段波荡器峰值磁场强度偏差必须小于FEL 参数\uf072  的二分之一，即0.025%。对于FEL-I，0.1nm 辐射FEL 参数\uf072为0.05%，波荡器  间隙16mm，因此要求波荡器间隙控制精度好于1.7\uf06dm。  隧道温度变化的影响：波荡器材料NdFeB 具有一定的温度系数，其峰值场  强随温度变化，变化量的最大允许值可由共振条件确定，对NdFeB 材料，温度  系数为10-3。可见，隧道温度变化必须控制在0.2 度以内。  波荡器段横向准直安装误差：平面型波荡器水平方向无聚焦，仅垂直方向有  聚焦，因此水平方向准直位置偏差对FEL 影响较小。而垂直方向位置偏差将导  致波荡器的等效强度减小，这一减小量的最大允许值可根据共振条件确定，  12

30. **private_use**，次数 9，`shine-accelerator-control-system-design-presentation`，物理页 20～20，Chunk `shine-accelerator-control-system-design-presentation:184c0d538e586c1a6583b965aac9deaf550b7aca453bdc683e51c2a66fe4376b`。

> 控制网络  \uf06e 控制网络是控制系统的神经系统  \uf06e 性能和可靠性是确保整个控制系统有效性的基础  \uf06e 核心交换机40\|100Gb/s，接入层交换机10Gb/s  \uf06e 核心交换机冗余，划分不同子网，按需要实施QoS  \uf06c控制主干网（万兆接入）  \uf06c设备本地网（千兆接入）  \uf06c图像专用网（GigE接口相机）  \uf06c存储专用网  \uf06c控制台专用网

## 页面异常样本

| 文档 | 物理页 | Chunk | 原始字符 | 图像 | 告警 |
|---|---:|---:|---:|---:|---|
| epics-documentation-latest-2026-08-18 | 2 | 0 | 0 | 0 | ['empty_text'] |
| epics-documentation-latest-2026-08-18 | 454 | 0 | 70 | 0 | [] |
| european-xfel-full-technical-design-report-2007 | 14 | 0 | 0 | 0 | ['empty_text'] |
| european-xfel-full-technical-design-report-2007 | 16 | 0 | 0 | 0 | ['empty_text'] |
| european-xfel-full-technical-design-report-2007 | 38 | 0 | 0 | 0 | ['empty_text'] |
| european-xfel-full-technical-design-report-2007 | 240 | 0 | 0 | 0 | ['empty_text'] |
| european-xfel-full-technical-design-report-2007 | 604 | 0 | 0 | 0 | ['empty_text'] |
| shine-accelerator-preliminary-design-report-2017 | 2 | 0 | 0 | 0 | ['empty_text'] |

## Stage 3 前的待处理事项

1. 按上表主要文档和物理页审查私用字符、替换字符与表格文本；保留原始证据，确认可恢复性后再修。
2. 对疑似扫描及无 Chunk 页面区分空白、图像页和文本提取失败；本阶段不做 OCR。
3. 复核连字符与 boilerplate 候选，再决定通用清洗修正；本报告不宣称版面和公式语义已经恢复。

## 可复现性与范围

版本记录：`{'head': '971bf45464b4fae5330109d1446470cd01eaadd7', 'dirty': True, 'identity_note': 'HEAD is a base commit, not the identity of this dirty run; see code hashes.'}`。工作树为 dirty 时，提交号仅表示基点。
语料仅包含 Registry 中的 PDF；未登记 PPTX/DOCX 不参与。百分位使用线性插值，页面分布包含没有 Chunk 的页面。
耗时记录见 retrieval baseline JSON；原始文档哈希、代码哈希和完整异常归属见本报告 JSON。

## 人工抽查与确认范围

- **formula_text_extraction_damage**：物理页 308 的原 PDF 中公式可见且清晰；对应 Chunk 含 166 个 U+FFFD。该页截图与提取文本对照表明损坏发生在文本提取结果中，不能用删除字符恢复公式语义。另两页为高计数异常，尚未逐式核对。

- **retained_running_header_and_page_number**：抽查确认固定页边窗口未覆盖部分实际页眉和页码位置，最终文本仍含重复报告标题和印刷页号。本轮测量并记录，未修改 cleaning 或算法版本。

- **isolated_numbers_are_not_all_page_numbers**：独立数字候选中包含信号数量表格；初步设计报告的物理页 309、311 也包含图轴刻度。因此 588 次只是形态命中，不能作为确认 footer 数量。

- **running_code_false_positives**：编号形态候选包含表格中的 T1/T2；其他样本包含设备名 CCN1 和有效术语 MSYS2。保留原文，等待位置与语义联合复核。

- **hyphenation_candidates_need_judgment**：634 次候选包括 non-linear、real-time 等真实复合词；无连字符拼写存在只构成候选依据，不能将计数称为已确认断词错误。

- **scanned_like_slide_false_positive**：已视觉核对：这是含原生可提取文字、内容较少的章节幻灯片，不应仅凭 possible_scanned_page 告警认定为扫描件或删除。物理页 34 亦为告警候选，未作扫描件确认。

- **large_report_order_sample**：已视觉核对该页章节和段落。单栏正文顺序样本未见明显颠倒；1730 个 Chunk 中仅 1 个短于 100 字符，不能据一个样本断言全书阅读顺序正确。

- **page_without_body_is_expected**：该页原始提取只有 EPICS Documentation、印刷页号和章节页脚，清洗后无 Chunk 与本页正文为空相符。

本轮清洗与切块保持 `pdf-chunks-v2`。正文提取存在已确认残留，但未为了改善审计数字临时增加文档特例。以上人工抽查补充于自动生成的统计之后，不代表全 corpus 逐页验收。


报告中的异常摘录是解析字符串的证据，控制字符与私用字符以码点转义显示；没有对公式进行转写或语义修复。此展示修正不改变 Chunk、向量或任何评测结果。
