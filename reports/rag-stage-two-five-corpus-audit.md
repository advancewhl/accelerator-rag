# RAG Stage 2.5 Corpus Quality Audit

生成日期：2026-10-19。算法：`pdf-chunks-v3`。
配置：`{'max_chars': 1200, 'min_chars': 300}`；阈值：`{'very_short_chars': 100, 'many_chunks_per_page': 10, 'example_limit': 100}`。

成功处理 13 份 PDF，共 2178 页、4537 个 Chunk、3755174 字符。统计保留短 Chunk；告警和候选污染不等于已确认错误。

## 每篇文档

| 文档 ID | 页数 | Chunk | 字符 | 空 Chunk 页 |
|---|---:|---:|---:|---:|
| epics-application-developers-guide-r3-16-2 | 354 | 848 | 741481 | 0 |
| epics-documentation-latest-2026-08-18 | 455 | 1071 | 926450 | 2 |
| european-xfel-full-technical-design-report-2007 | 646 | 1730 | 1469169 | 5 |
| european-xfel-undulator-commissioning-spectrometer-cdr-2011 | 21 | 41 | 32036 | 0 |
| european-xfel-x-ray-optics-beam-transport-tdr-2012 | 164 | 235 | 169328 | 0 |
| european-xfel-standard-e-beam-diagnostics-linac2010 | 3 | 13 | 12438 | 0 |
| shine-epics-ioc-pv-information-management-pcapac2022 | 3 | 13 | 11677 | 0 |
| shine-accelerator-fast-interlock-2024 | 9 | 18 | 15651 | 0 |
| shine-control-system-status-icalepcs2019 | 4 | 15 | 13895 | 0 |
| shine-cryogenic-control-system-2021 | 8 | 22 | 18792 | 0 |
| shine-white-rabbit-beam-synchronous-timing-ipac2022 | 5 | 17 | 15196 | 0 |
| shine-accelerator-control-system-design-presentation | 34 | 34 | 5965 | 0 |
| shine-accelerator-preliminary-design-report-2017 | 472 | 480 | 323096 | 4 |

## 长度与页面分布

| 统计量 | Chunk 字符数 | 每页 Chunk 数（含 0） |
|---|---:|---:|
| min | 1 | 0 |
| p10 | 384.6 | 1.0 |
| p25 | 605.0 | 1.0 |
| median | 897.0 | 2.0 |
| p75 | 1078.0 | 3.0 |
| p90 | 1164.0 | 4.0 |
| p95 | 1184.0 | 4.0 |
| max | 1200 | 6 |
| mean | 827.6777606347807 | 2.0831037649219466 |

极短 Chunk：49；超长 Chunk：0。
无 Chunk 页面：11；超过每页数量阈值的页面：0。

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
| null | 0 |  |
| private_use | 299 | shine-accelerator-control-system-design-presentation: 170; shine-accelerator-preliminary-design-report-2017: 65; european-xfel-x-ray-optics-beam-transport-tdr-2012: 64 |
| publication_identifiers | 2 | european-xfel-full-technical-design-report-2007: 2 |
| copyright_license | 21 | epics-documentation-latest-2026-08-18: 13; shine-cryogenic-control-system-2021: 7; european-xfel-undulator-commissioning-spectrometer-cdr-2011: 1 |
| isolated_page_numbers | 123 | shine-accelerator-preliminary-design-report-2017: 75; european-xfel-full-technical-design-report-2007: 14; shine-accelerator-fast-interlock-2024: 12 |
| running_publication_codes | 19 | shine-accelerator-preliminary-design-report-2017: 13; european-xfel-x-ray-optics-beam-transport-tdr-2012: 5; epics-documentation-latest-2026-08-18: 1 |
| suspicious_hyphenation | 634 | european-xfel-full-technical-design-report-2007: 389; epics-documentation-latest-2026-08-18: 120; epics-application-developers-guide-r3-16-2: 36 |

内部连字符仅在 corpus 中存在无连字符拼写时列为候选；可能包含真实复合词。出版编号、版权词和独立数字也可能出现在有效正文中。审计不修改文本。

## 三类重点文档

### The European X-Ray Free-Electron Laser Technical Design Report

646 页、1730 个 Chunk；无 Chunk 页面 5。
告警：`{'empty_text': 5, 'possible_garbled_text': 4}`。清洗后质量信号：`{'replacement': 0, 'null': 0, 'private_use': 0, 'publication_identifiers': 2, 'copyright_license': 0, 'isolated_page_numbers': 14, 'running_publication_codes': 0, 'suspicious_hyphenation': 389}`。
Chunk 长度：`{'count': 1730, 'min': 54, 'max': 1200, 'mean': 849.2306358381503, 'p10': 453.0, 'p25': 660.0, 'median': 902.0, 'p75': 1067.75, 'p90': 1158.0, 'p95': 1183.0, 'very_short_chunks': 1, 'very_long_chunks': 0}`。

### 硬 X 射线自由电子激光装置初步设计报告（加速器分册）

472 页、480 个 Chunk；无 Chunk 页面 4。
告警：`{'empty_text': 1, 'private_use_characters': 23, 'possible_garbled_text': 39}`。清洗后质量信号：`{'replacement': 1017, 'null': 0, 'private_use': 65, 'publication_identifiers': 0, 'copyright_license': 0, 'isolated_page_numbers': 75, 'running_publication_codes': 13, 'suspicious_hyphenation': 4}`。
Chunk 长度：`{'count': 480, 'min': 2, 'max': 1200, 'mean': 673.1166666666667, 'p10': 381.9, 'p25': 506.0, 'median': 654.0, 'p75': 845.25, 'p90': 991.8000000000002, 'p95': 1079.3999999999996, 'very_short_chunks': 8, 'very_long_chunks': 0}`。

### SHINE 加速器控制系统设计与开发

34 页、34 个 Chunk；无 Chunk 页面 0。
告警：`{'private_use_characters': 30, 'possible_scanned_page': 2}`。清洗后质量信号：`{'replacement': 0, 'null': 0, 'private_use': 170, 'publication_identifiers': 0, 'copyright_license': 0, 'isolated_page_numbers': 0, 'running_publication_codes': 0, 'suspicious_hyphenation': 0}`。
Chunk 长度：`{'count': 34, 'min': 3, 'max': 388, 'mean': 175.44117647058823, 'p10': 68.0, 'p25': 123.0, 'median': 159.5, 'p75': 226.0, 'p90': 294.7, 'p95': 307.4, 'very_short_chunks': 8, 'very_long_chunks': 0}`。

## 高优先级异常样本

以下样本优先展示乱码、NULL 和私用字符，其次为版权词与断词候选。示例经过截取，精确位置与完整页面统计见同名 JSON。

1. **replacement**，次数 166，`shine-accelerator-preliminary-design-report-2017`，物理页 308～308，Chunk `shine-accelerator-preliminary-design-report-2017:2119956386059a9909003e07de59e3a5401a2bb3b6f29432d66c690cd54e776b`。

> 图3.3.6.1-30 束流倾角入射示意图  对整个腔体长度进行积分，得到束流倾角入射时在腔体内激发的信号如下所  示：  ��= A  −�  2  � 2 ����� න �−  �+ � �����  2� �����+ � �����  ��  �  =  �����  � �−  �  2� −�  2  � 2 � ׬ �−  � �����  2� ��������  ��  �����+ ��������  ��  ����� dz  当条件2\uf070 \uf074 \uf077\uf03c\uf03c 时，即腔体谐振信号周期远小于衰减时间常数时，积分项内当z  从-L/2 到L/2，�  �  −�����  2�项结果均近似为1，因此可简化成：  ��≈  �����  � �−  �  2� −�  2  � 2 � ׬ ��������

2. **replacement**，次数 151，`shine-accelerator-preliminary-design-report-2017`，物理页 310～310，Chunk `shine-accelerator-preliminary-design-report-2017:9f2ae54d8aa5a8d641ea3cc6ca033c924a41bde166fe3c6b20ef8ebbff264dea`。

> ��= A �−������−�  2�������� �  图3.3.6.1-33 束流倾角入射示意图  对整个腔体长度L 进行积分，得到：  ��= A  −�  2  � 2 ����� න �−  �+ � �����  2� �����+ � �����  ��  �  = �����  � �−�  2������ 2�2���2� �2 ��� �� 2�����−������ � ��� �� 2�����  −�����  �  2����� � ��� �� 2������−� 2������  从公式中可知此种情况下分解成了两部分，第一部分和公式（7）相同，等  效成束流

3. **replacement**，次数 115，`shine-accelerator-preliminary-design-report-2017`，物理页 312～312，Chunk `shine-accelerator-preliminary-design-report-2017:f82b231d3421be698e7f2b56a0199e8a7bedc5d6db1f664bda04d9d1abb0d3ee`。

>   设束团长度为 z \uf073，束团电荷量为q ，束团自身倾角为\uf061，等效结果可视为  将束团分割成一组组带电量为dq 的电子沿z 轴分布，则每组电子的位置偏移量  为�tan �假设束团呈高斯分布，则有：  ��= q  2π�� �  −�2  2��2��  结合此前公式，则有：  ���= ω  2 � ����  ( �  �)0�  −�2��2  �2 �tan (�)  �0  �−�  2�sin ωt ��  = �tan (�)  2��� ��  −�2  2��2�−� 2�sin ωt ��  积分得：  ��= �tan (�)  2��� −∞  +∞  ��  −�2  2��2�− �−�  � 2� sin ω �−�  � �� න  = �tan (�)  2��� �−�  2�  −��  +��  ��  −�

4. **replacement**，次数 47，`shine-accelerator-preliminary-design-report-2017`，物理页 325～325，Chunk `shine-accelerator-preliminary-design-report-2017:54749b94482f46d1c3e087124c6ea2f8f7877ebe4e11aa9e845ee3b5b7707c6b`。

> 用重火石玻璃（SF-11）  作为光学展宽器。激光通过重火石玻璃，由于群速度色散（GVD 效应），出射激  光脉冲宽度将会展宽，展宽宽度与介质厚度的关系为：  ��= �0 1 + 2��2 ��  ���2  �0  2  其中：T0 为原始激光脉宽。通过选择合适的介质厚度，可以得到所需的激光  脉冲宽度。  （2）电光调制  考虑到激光与库伦电场在晶体中的速度不匹配、晶体对库伦电场的衰减及晶  体表面的反射折射影响，可得晶体的响应函数为：  ��= 2 1 + ��+ ��(�) 1 �  0  �  −∞  +∞  ����2���  � ���−��� ���−2���(�)�/����� න න  对应不同厚度的GaP 晶体的响应函数曲线，当选择晶体厚度在0.1mm  以内时，将得到较平坦的响应曲线，如图3.3.6.1-44 所示[7]。考

5. **replacement**，次数 46，`shine-accelerator-preliminary-design-report-2017`，物理页 83～83，Chunk `shine-accelerator-preliminary-design-report-2017:236a227e1101bfab2e32bdc135b766a9c399c3ad8332d18038ab99ffad8b0418`。

> 位置的剩余磁场要小于0.5μT，即5 mG，式中R0=3.6 nΩ/μT，R1=0.75×10-2  nΩ/μT/mT。  ����= ��+ ��������  超导腔的最佳耦合度与束流强度相关，一般设计使建立腔压所需的功率最小。  当加速梯度Eacc=16MV/m、Q0=2.7×1010，峰值麦克风效应引起的频率失谐为δf=10  Hz 时，利用下式可以求出最佳耦合度βopt=656，进而得到此时耦合器的外部品质  因数为Qe=4.12×107。  ����= [ �+ ����(�/�)  ��  �  + �����  ��  �  ]�/�  ��= ��/����  （2）3.9GHz 超导腔  SCLF 将安装16 支3.9GHz 超导腔，在2K 工作下，加速梯度14MV/m、  Q0=2.0×109

6. **replacement**，次数 46，`shine-accelerator-preliminary-design-report-2017`，物理页 307～307，Chunk `shine-accelerator-preliminary-design-report-2017:5cf0761c29335b2b5fce79573318d665f1bc90077f9f81b0500adb8d4d28678f`。

> z 的  小谐振腔，则腔体中激励信号即是一个个小谐振腔激励信号的积分的结果。  当束流沿平行中心轴偏离电中心距离为x入射时，腔体激励信号电压由公式  所示：  ��= ωqx  2x0  Z �  � �0  �  −�2��2  �2 �−�  2�sin ��  其中 0 [ ] R Q 是当束流偏离腔体电中心x 时的分流阻抗，假设此过程中束团长  度条件不变，腔体参数也固定，可将常数项分离，令：  �= ωq  2x0  Z �  � �0  �  −�2��2  �2  则有：  ��= ���−�  2�sin ��  当束流按一定的倾角θ经过腔体中心时，其模型可如图3.3.6.1-30 所示，则腔  长为dz 的小腔体的激励电压为：  ��= ��tan ��−�  2�sin ���� �

7. **replacement**，次数 33，`shine-accelerator-preliminary-design-report-2017`，物理页 324～324，Chunk `shine-accelerator-preliminary-design-report-2017:341f706f6f5341da02a3d868e24b8134fc989dee8e829e34f368016034953131`。

> 的是，在束团长度100fs 或更短时，由于  Chirp 调制引入的边带，导致在频域的反卷积过程中得到束团的长度信息时引入  过大噪音，在原理上存在分辨率极限Δ�= 2.6 �0��，其中T0,Tc 分别表示激光展  宽前后的脉冲宽度。  FELIX 在此基础上发展了一不依赖于探测激光稳定性，同时可克服边带影响  的时域解码方法，并可直接得到束团的时域长度，基本结构如图3.3.6.1-43所示[4,5]。  图3.3.6.1-43 单次通过时域解码束长测量系统  从探测激光出来的激光被分成两束，其中一束类似频谱解码法（EO 光），通  过光学展宽器、起偏器、电光晶体、偏振片、最后到达BBO 晶体；另一束（gate  光）通过与EO 光相同的光程到达BBO 晶体，光路上安装一可调光路延时线用  于精确调节光程使两束光同时到达BBO 晶体。两束光以特定夹

8. **replacement**，次数 29，`shine-accelerator-preliminary-design-report-2017`，物理页 331～331，Chunk `shine-accelerator-preliminary-design-report-2017:44971fb667b10278bdb6707fcd5976fc979fe3efd00722504e52e6e05cec2e40`。

>  腔式探头结构  （1）设计指标与技术参数  对于BAM 测量，腔体引出的信号通过RF 前端进行IQ 解调，量化后得到相  对于参考信号的到达时间信号如下：  ��=  arctg ����  ���� 2��010  考虑到测量噪音，最好通过适当的延迟参考信号到达BAM 探头的时间，使  得测量时信号的实部接近0，虚部最大，此时BAM 测量系统的时间分辨率如下：  Δ�= 1 2��0 × ���+ �  2��0 × �� 2 + ������  上式中，第一项来自于测试信号的信噪比对测量结果的干扰；第二项来自于  有限测量时长对频率测量精度的影响；第三项来自于参考信号到达BAM 探头的  时间抖动，基于激光的飞秒同步系统可以提供jitter 小于20fs 的参考信号。虽然  来自腔体的信号在1nC 电荷量情况下高达120dB，但考虑到量化噪音及

9. **replacement**，次数 26，`shine-accelerator-preliminary-design-report-2017`，物理页 328～328，Chunk `shine-accelerator-preliminary-design-report-2017:6ddec15232a05302bd07465d1b26f848c496d072d95eb717a4527c7fe0506759`。

> 一定波长情况下，具有相干性，为  相干叠加。不同距离电子的同步辐射的相干性，随着距离的增加，或者辐射波长  的减小，而逐步减少。故最终同步辐射的总功率，为：  �(�) = �0(�) �+ �(�−1)�(�)  �(�) =  −∞  +∞  �(�)����2�  �������� න  2  其中，q(z)为束团的纵向归一化分布函数，N 为束团粒子数；P0(λ)为单粒  子通过该弯转处在波长λ的辐射功率。在一定带宽内及知道束团能量的情况下，  若能同时测得辐射的总功率，以及束团电荷量，便能求得束长函数q(z)。  系统的基本结构如图3.3.6.1-46 所示：

10. **replacement**，次数 26，`shine-accelerator-preliminary-design-report-2017`，物理页 252～252，Chunk `shine-accelerator-preliminary-design-report-2017:a80d401562c66145f109d576062cfba6f2ba764a15c484e04e623041e7077db3`。

> -seeding 光栅单色器采用环面的变线  距光栅，环面光栅使得光栅单色器子午聚焦在狭缝处，弧矢方向聚焦在第二级波  荡器的入口处，根据环面镜的聚焦公式:  ��=  2  �����（  ��� �+��）,��= 2�����  ��� �+��  可以得到光栅子午和弧矢方向的半径，同时光栅采用的是变线间距的光栅，  采用变线距光栅有很多好处，可以总结为：  可以简化光路，减少一些不必要的光学元件；  相比于平面光栅，变线距光栅可以提高光学的传输效率；  变线距光栅可以消除光学像差，提高成像质量；

11. **replacement**，次数 25，`shine-accelerator-preliminary-design-report-2017`，物理页 326～326，Chunk `shine-accelerator-preliminary-design-report-2017:53e3b8f53e6d8134315b11a44616f6c11941a9eda275cbdf29fa49b2afe139d3`。

> ����(�) = ����[�(�)�(�)]  由晶体的响应函数曲线可知，采样的有效库伦电场幅度约为入射电场幅度的  一半。  （3）BBO 晶体二次谐波产生  对于二次谐波产生，拟选用偏硼酸钡（BBO）晶体。BBO 晶体具有透明区  域大、相位匹配范围大、非线性系数大、损坏阈值高、热吸收带宽大、光学均匀  性好等优点。  图3.3.6.1-45 BBO 晶体二次谐波产生  具体方案拟采用非共线I 型相位匹配（o+o→e）方案，如图3.3.6.1-45 所示：  假设BBO 晶体的主轴与晶体表面法线的夹角为Θ，两入射光对称入射，夹角大  小为2Φ，两入射光均为水平偏振光，出射光为竖直偏振光

12. **replacement**，次数 24，`shine-accelerator-preliminary-design-report-2017`，物理页 82～82，Chunk `shine-accelerator-preliminary-design-report-2017:da655e63f84dbccb1fcb61bea62c1c9ca48c6c1e256f641334389ac67a165b16`。

> ，与加速腔压Vc 成正比，曲线如图3.3.3.2-3 所示，Eb=8.0GeV，所  以为降低建造和运行成本，亟需提高超导高频腔的无载品质因数降低动态功耗。  ��������= ���  �  �/�× ��  = ���� �/�× ��  图3.3.3.2-3 SCLF 超导直线加速器总低温动态功耗与超导腔品质因数关系  SCLF 计划采用高纯铌材，利用冲压和电子束焊接成型，然后进行电抛光结  合氮掺杂的表面处理和一系列表面处理流程和洁净组装工艺，保证获得高Q 值  的超导铌腔。在制造前必须对所采用优质高纯铌材进行全面检测，从原材料上严  格把关，以保证超导腔的性能，表面有缺陷的铌材则直接淘汰，严禁进入下一个  制造环节。电子束焊接成型的哑铃，需观察焊缝确保无焊接缺陷，同时利用专用  测量设备测量谐振频率和哑铃高度，偏差大的哑铃不能进入整腔的电

13. **replacement**，次数 23，`shine-accelerator-preliminary-design-report-2017`，物理页 196～196，Chunk `shine-accelerator-preliminary-design-report-2017:22453407a9916aba39f97df8ad41ce20f3db563a8bc209b92e6eea95a84334db`。

> mcollimation~80�，可得在septum 入口处的束流垂直偏移约为  �= �������+ 2������������εβseptum ≈15��  在此要求的基础上，我们采用总共10 块kicker 磁铁，每五块为一组，分别  放置于两块四极磁铁中间。每块kicker 磁铁的角度为0.1mrad，总偏转角度为  1mrad。由于四极磁铁的磁中心位于直通线上，因此经过kick 后的束流会偏轴经  过四极磁铁，感受到一定的二极场分量，一定程度上改变了实际的偏转角度。经  过模拟研究，在如图3.3.4.2-2 所示的布局条件下，产生的垂直方向轨迹，可以满  足septum 入口束流垂直偏移的要求。  图3.3.4

14. **replacement**，次数 21，`shine-accelerator-preliminary-design-report-2017`，物理页 315～315，Chunk `shine-accelerator-preliminary-design-report-2017:6967997551e4db045f95d76d65f18f014b46a130056e123b2242c40908b81c02`。

> ′以及和  2 号腔体测出的束团位置U2 进行对比并采用统计学的方法进行位置分辨率的评  估。验收原理可由图3.3.6.1-41 和以下方程表示：  U2 = �12 × �3 + �23 × �1 /�13  δ����= ��× ���Δ�  ��= 1  �23 �13  2 + �12  �13  2 + 1  图3.3.6.1-41 系统性能指标验收评估示意图  6.1.3.3.7 系统研制风险与控制  前期为了SDUV、DCLS、SXFEL 的位置测量进行了CBPM 系统的研发，  积累了丰富的经验。腔体在加工上对频率和Q 值的要求需严格控制，前期已完  成相当多的加工实验工作，腔体设计加工上基本无风险。系统研制过程中着重射  频前端引入噪声大小问题，验收需严格测试以及现场安装需关注电磁屏蔽问题。  6.1.3.4 检测设施  6.1.3

15. **replacement**，次数 19，`shine-accelerator-preliminary-design-report-2017`，物理页 261～261，Chunk `shine-accelerator-preliminary-design-report-2017:58c987241ef48c355e7fd9ab6ededafde85bd8019d9503350c1a4223ed1e804e`。

> （取n=1）：  �� ����= ��  �  由此可以估算（111）面的单色带宽：光子能量为3.05 keV 时，  ��  �≈ 500�−6  tan 80.75° = 8.1�−5  光子能量为7 keV 时，  ��  �≈ 30�−6  tan 25.47° = 6.3�−5  由两图还可以看出，当光子能量在3keV 左右时C(1,1,1)的透射率较低，故  此时应采用尽量薄的晶体。  图3.3.4.8-11 100μm 厚的C(1,1,1)晶体对3keV（a）和7keV（b）的吸收曲线。  图3.3.4.8-12 50μm 厚的C(1,1,1)晶体对3keV（a）和7keV（b）的吸收曲线。

16. **replacement**，次数 19，`shine-accelerator-preliminary-design-report-2017`，物理页 409～409，Chunk `shine-accelerator-preliminary-design-report-2017:7d0bf7d6f450f58639ae8e1bafa7a7c39a982eef60ab3e5fe8f806e4d583d149`。

>  使相位关系又回到开始，从而保证能量流动方向不变。我们采用的是熔融法生长  的晶体，对应的包括1550nm 和775nm 在内的Sellmeier 公式为：  ��  2 λ = 2.0993 + 0.922683  1 −0.467695 �2  −0.0138408�2  ��  2 λ = 2012725 + 1.18431  1 −0.0514852 �2  + 0.6603  1 −100.00507 �2  −0.00968956�2  相位匹配是实现和频输出的充分必要条件，而PPKTP 晶体工作于准相位匹  配条件下。在一个相干周期内，两路入射光和和频光的波数之和不为零，即不能  实现相位匹配，因此能量不能够稳定输入到和频光使之实现放大。解决这个问题  的办法是，在相位变化到和频光强度恰好要开始降低时将磁化方向翻转180 度，  使相位

17. **replacement**，次数 18，`shine-accelerator-preliminary-design-report-2017`，物理页 256～256，Chunk `shine-accelerator-preliminary-design-report-2017:c82725130247eb91094362f287057a1600d953d65f17b9cf7876f97230a29d1b`。

> g 的光谱宽度可以  达到10-4 以下。  除了能量分辨率，光栅单色器设计还要求单色器要有较高的传输效率。光栅  单色器的衍射效率可以用以下公式进行计算：  �0 = �  4 (1 + 2 1 −����4�ℎ���� � + (1 −�)2)  由此可以得出所设计的光栅单色器的衍射效率为0.0365，当光栅经过某个光学元  件的时候，其反射效率可以用以下公式进行计算:  �= ( �1 −�2  �1 + �2  )2  光栅单色器的反射效率和原子散射因子、入射角、衍射波长有关，若选取金作为  基底，当光子能量为1keV 时，可以得到平面镜的反射效率约为0.9595，从而得  到光栅单色器的整体传输效率约为0.0303。  （3）单色器机械结构设计  根据软线self-seeding 方案中的机械扫描图3.3.4.8-2 可以看出在扫描的过程 

18. **replacement**，次数 17，`shine-accelerator-preliminary-design-report-2017`，物理页 352～352，Chunk `shine-accelerator-preliminary-design-report-2017:49e5de036f589efe55fb41140cc5a85d0c00bd6a94b76a1b938f3fe6efbfd61b`。

> 丝，U 方向扫描丝，X 方向扫描丝依次扫过束流，同步采集丝靶位置数据  及丝扫描探头后方的束损探头上的束损信号即可重建出束流截面。  扫描丝的温度公式如下：  �(�) = ��  ��  � 2����⊥  1 ��  dE: 沉积能量  I: 流强  ��: 热容  �⊥: 截面尺寸  �: 冷却因数  碳的熔点为3550℃，热容为0.42cal/g/℃;钨的熔点为3410℃，热容为  0.055cal/g/℃，所以钨和碳是适合的材料。为了防止温度过高导致扫描丝熔断，  扫描速度应该尽量快，需要选用速度快的电机。另外，由于丝扫描探头的RMS  分辨率由扫描丝的直径决定，为D/4，所以扫描丝应该尽可能细，考虑到当前加  工水平以及丝的强度，扫描丝的直径定为4-10μm。丝扫描的位置数据需要和束  损信号精确同步，通过基于事件码的系统实现。每个丝扫描

19. **replacement**，次数 17，`shine-accelerator-preliminary-design-report-2017`，物理页 460～460，Chunk `shine-accelerator-preliminary-design-report-2017:4aa9717b5fddff8ab4951ed2d1c80bf811c3921dd83cafd105378172a6540abc`。

> 在十分钟内，可信  度为95%时的分辨率）。  （3）输出电压纹波  在实际负载下测试，使用示波器在电源输出端进行测量，输出电压纹波的测  试。计算公式为：  ��=  ��−�  ��  这里vp-p为输出电压波动的峰峰值，需要考虑特定的频率下的输出电压纹波，  低频市电整流纹波和高频的电源开关纹波，可以按照示波器直接检测或者通过示  波器的FFT 功能读取特定频率的幅值，作为输出电压波动的幅值。V0 为被测电  流时的电源输出直流电压值。  测量范围：(20~100)% 额定电压。  （4）电流纹波测试  通过电压纹波的幅值和特定频率下的电感的感抗相比较得到电源的电流纹  波，由于不同的负载采用同一电源所以约定按照负载30mL 的电感量来衡量电源  输出电流的纹波值。  输出电流纹波包括：低频（交流电50Hz 的倍频成分）纹波电流和高频（开  关

20. **replacement**，次数 16，`shine-accelerator-preliminary-design-report-2017`，物理页 410～410，Chunk `shine-accelerator-preliminary-design-report-2017:4d2c6dbbff18da4a6c01bc9d6bed3ba2e3fe95aaf93a5f3fc9886ca60b23a628`。

> ����= 1 ��(�2)  �2  −��(�1)  �1  −��(�1)  �1  其中，λ为波长，单位μm，λ1 为1.55μm，λ2 为0.775μm，ny，nx 分别为晶体  y 轴和x 轴的折射率，Lyxy 为满足准相位匹配调节需要的晶体的周期长度，单位  为μm。  通过计算得到晶体的周期长度为46.22μm。根据理论分析并考虑成本，选取  晶体的长度为5mm。  （3）光纤稳相控制系统设计方案  锁模光纤激光器输出的参考激光脉冲透过PBS 的部分经过一个四分之一波  片（QWP）和反射镜（DM）返回，重新入射到PBS 时，光的偏振方向刚好旋  转90°，可以由PBS 反射，

21. **private_use**，次数 30，`shine-accelerator-control-system-design-presentation`，物理页 26～26，Chunk `shine-accelerator-control-system-design-presentation:e1c35529e291cca970425ed8236272f89c4baf39b52b11de0bb8516839d73add`。

> 运行与开发环境  \uf06e 为整个控制系统提供运行环境  \uf06e 由服务器集群、存储设备、网络设备等组成  \uf06e 采用虚拟服务器和实体服务器相结合的方式  \uf06e 提供各类基础服务，如账号管理、文件管理、时间同步等  \uf071\uf020软件开发管理  \uf073\uf020开发过程记录与控制  \uf073\uf020开发流程优化与简化  \uf071\uf020通道信息管理  \uf073\uf020通道信息采集与存储  \uf073\uf020通道状态监控与管理  \uf071\uf020通道权限管理  \uf073\uf020通道访问权限管理  \uf073\uf020通道访问记录存储与显示  \uf071\uf020网络管理与监测  \uf073\uf020网络地址分配与管理  \uf073\uf020交换机及端口的管理  \uf073\uf020网络传输效率的监测

22. **private_use**，次数 14，`european-xfel-x-ray-optics-beam-transport-tdr-2012`，物理页 153～153，Chunk `european-xfel-x-ray-optics-beam-transport-tdr-2012:940907d2f9c34eefa8ad8780aa3e9f00ae523cabb22d6dc3fc29a053dbdddd85`。

> elated documentation  For some of the documents in “EDMS”, a login is required. \uf069  The following documents provide additional technical documentation:  \uf06e “CDR: X-Ray Optics and Beam Transport” (EDMS D*2081421)  \uf06e “UHV Guidelines for X-Ray Beam Transport Systems”  \uf06e “CAD Integration Guidelines for Photon Beamline Components”  \uf06e “Beam transport component list” (EDMS D*2278111)  \uf06e

23. **private_use**，次数 11，`shine-accelerator-control-system-design-presentation`，物理页 15～15，Chunk `shine-accelerator-control-system-design-presentation:4c5c714be0cc0e17c3b7314656a75887600edfab1f96f8d6cea58cf040b4ee53`。

> SHINE 加速器控制系统  \uf06e 设备控制  \uf06e 数据采集  \uf06e 机器联锁  \uf06e 定时系统  \uf06e 控制网络  \uf06e 运行环境  \uf06e 数据存储  \uf06e 用户界面  \uf06e 上层软件  \uf06e 反馈系统  \uf06e 中央控制室  加速器控制系统：  1. 实施对注入器、超导加速  器、束流分配、波荡器系统  中各类设备的全面控制  2. 提供硬X射线自由电子激  光装置调试和运行的平台  3. 满足加速器物理学家、工  程技术人员对设备监控、数  据获取与分析等方面的需求

24. **private_use**，次数 10，`shine-accelerator-control-system-design-presentation`，物理页 17～17，Chunk `shine-accelerator-control-system-design-presentation:3942887566f2fb2abd46d9f69eaf29185e83d71b2903f06438cefdbabc853d0a`。

> 数据采集  \uf06e 图像采集、波形数据采集是控制系统的组成部分  \uf06e 图像采集：束流测量系统、驱动激光系统、种子激光系统、光学诊断系统等  \uf06e 常规图像采集 (areaDetector)  \uf06cGigE Vision 接口相机  \uf06c图像专用传输网络  \uf06c在线采集、处理、存储  \uf06e 高帧率图像采集  \uf06cCamera Link 接口相机  \uf06c点对点连接方式  \uf06c在线采集、存储；离线处理、分析  SXFEL束流截面测量

25. **private_use**，次数 10，`shine-accelerator-preliminary-design-report-2017`，物理页 190～190，Chunk `shine-accelerator-preliminary-design-report-2017:7d63c9bac942094d94e39a58f2da12ab0ec73393db50b6c9b984085fe92ed037`。

> 个平  衡点。  波荡器磁场整体偏差及气隙控制精度：不同波荡器段之间的磁场整体误差要  求可以根据共振条件确定，不同段波荡器峰值磁场强度偏差必须小于FEL 参数\uf072  的二分之一，即0.025%。对于FEL-I，0.1nm 辐射FEL 参数\uf072为0.05%，波荡器  间隙16mm，因此要求波荡器间隙控制精度好于1.7\uf06dm。  隧道温度变化的影响：波荡器材料NdFeB 具有一定的温度系数，其峰值场  强随温度变化，变化量的最大允许值可由共振条件确定，对NdFeB 材料，温度  系数为10-3。可见，隧道温度变化必须控制在0.2 度以内。  波荡器段横向准直安装误差：平面型波荡器水平方向无聚焦，仅垂直方向有  聚焦，因此水平方向准直位置偏差对FEL 影响较小。而垂直方向位置偏差将导  致波荡器的等效强度减小，这一减小量的最大允许值可根据共振条件确定，  12

26. **private_use**，次数 9，`shine-accelerator-control-system-design-presentation`，物理页 20～20，Chunk `shine-accelerator-control-system-design-presentation:5aace5681eef8197acdf6ae2becdde6c29a9cd45a19d72afcf6c40f6f325ff20`。

> 控制网络  \uf06e 控制网络是控制系统的神经系统  \uf06e 性能和可靠性是确保整个控制系统有效性的基础  \uf06e 核心交换机40\|100Gb/s，接入层交换机10Gb/s  \uf06e 核心交换机冗余，划分不同子网，按需要实施QoS  \uf06c控制主干网（万兆接入）  \uf06c设备本地网（千兆接入）  \uf06c图像专用网（GigE接口相机）  \uf06c存储专用网  \uf06c控制台专用网

27. **private_use**，次数 9，`shine-accelerator-control-system-design-presentation`，物理页 23～23，Chunk `shine-accelerator-control-system-design-presentation:87679a634ae718d54dbf09b8a713f86bfd3903ce1f528437356ce3ad8e34c6f9`。

> 联锁系统  \uf06e 快联锁样机  \uf06c综合考虑稳定性、工程周期等因素，拟采用成熟、稳定的工业级FPGA板卡进行构建  \uf06c指标：站点内关键信号响应时间≤10us，站点间关键信号响应时间≤100us  \uf06c目前在评估cRIO、PXIe等硬件平台  \uf06e 运行模式管理（30+）：  \uf06c低重复频率运行模式 (0 ~ 100Hz)  \uf06c中重复频率运行模式 (0.1 ~ 100kHz)  \uf06c高重复频率运行模式 (0.1 ~ 1MHz)  \uf06c停机模式、RF老练、激光调试等模式  联锁条件：低重复频率运行模式 ⊂ 中重复频率运行模式 ⊂ 高重复频率运行模式  停机模式 RF老练 调试模式  注入器 调试模式  超导加速器  调试模

28. **private_use**，次数 7，`european-xfel-x-ray-optics-beam-transport-tdr-2012`，物理页 120～120，Chunk `european-xfel-x-ray-optics-beam-transport-tdr-2012:ca320e7add55021e1b5f0fbb37a3feb804da6fe603a2e6343f3e541c45bfea98`。

> ist shows the main components that are operated by the  vacuum control system:  \uf06e Vacuum pumps (scroll, turbo, getter ion, NEG)  \uf06e Vacuum gauges  \uf06e Gate valves, fast safety valves  \uf06e SASE3 gas attenuator  \uf06e Differential pumping units  \uf06e Residual gas analysers (RGA)  \uf06e Other sensors (temperature, air pressure, cooling water flow)  The control system itself consists of a central 

29. **private_use**，次数 7，`shine-accelerator-control-system-design-presentation`，物理页 7～7，Chunk `shine-accelerator-control-system-design-presentation:349e26105084642c8780e411c5830fc6d4f1bc3bb70fe9b1622e4de7294bcd47`。

> 加速器控制系统总体规模  \uf06e 被控设备数量～9000，其中嵌入式IOC～1200  软线实验装置～700，其中嵌入式IOC～60  \uf06e PV数量～1M（按每个设备对应～100个通道估算）  软线实验装置～100K  \uf06e 控制网交换机～370台，其中设备控制网～230台  软线实验装置～10 + 40台；上海光源～30 + 10台  \uf06e 串口服务器～200台  \uf06e 联锁系统信号规模～6000  软线实验装置～1000；上海光源～3000 \|～3人  \uf06e 模组本控信号规模～6000  \uf06e 定时信号～1200路，节点数～600  软线实验装置～55路，用户装置～140路

30. **private_use**，次数 7，`shine-accelerator-control-system-design-presentation`，物理页 16～16，Chunk `shine-accelerator-control-system-design-presentation:79aa24c47609dc2c6465887776611981e9b3dbdd69477338ed6ba8f5999d8597`。

> 设备控制  \uf06e 设备控制是整个控制系统的核心和基石  \uf06e 实施对注入器、超导加速器、束流分配、波荡器系统中各类设备全面、有效的控制  \uf06e 拥有SSRF、DCLS、SXFEL、Sirius Linac等装置控制系统开发基础和成功经验  \uf06c稳定可靠的工业级IOC控制器  \uf06c高效的设备控制专用网络  \uf06c友好的操作员界面  \uf06c严格的接口标准与规范

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
| shine-accelerator-preliminary-design-report-2017 | 6 | 0 | 28 | 0 | [] |
| shine-accelerator-preliminary-design-report-2017 | 166 | 0 | 30 | 0 | [] |
| shine-accelerator-preliminary-design-report-2017 | 278 | 0 | 30 | 0 | [] |

## Stage 3 前的待处理事项

1. 按上表主要文档和物理页审查私用字符、替换字符与表格文本；保留原始证据，确认可恢复性后再修。
2. 对疑似扫描及无 Chunk 页面区分空白、图像页和文本提取失败；本阶段不做 OCR。
3. 复核连字符与 boilerplate 候选，再决定通用清洗修正；本报告不宣称版面和公式语义已经恢复。

## 可复现性与范围

版本记录：`{'head': '971bf45464b4fae5330109d1446470cd01eaadd7', 'dirty': True, 'identity_note': 'HEAD is a base commit, not the identity of this dirty run; see code hashes.'}`。工作树为 dirty 时，提交号仅表示基点。
语料仅包含 Registry 中的 PDF；未登记 PPTX/DOCX 不参与。百分位使用线性插值，页面分布包含没有 Chunk 的页面。
耗时记录见 retrieval baseline JSON；原始文档哈希、代码哈希和完整异常归属见本报告 JSON。

## 确定性清洗结果

`{'null_before': 4, 'null_after': 0, 'replacement_before': 1017, 'replacement_after': 1017, 'replacement_chunks': 39, 'pua_policy': 'Unexplained PUA preserved; insufficient multi-document evidence for safe bullet mapping.'}`

## Retrieval eligibility

```json
{
  "config": {
    "replacement_ratio": 0.2,
    "minimum_replacements": 8
  },
  "total_chunks": 4537,
  "eligible_chunks": 4532,
  "ineligible_chunks": 5,
  "ineligible_by_reason": {
    "number_or_running_code_only": 1,
    "boilerplate_only": 1,
    "mostly_replacement_chars": 3
  },
  "per_document_ineligible": {
    "epics-application-developers-guide-r3-16-2": 1,
    "shine-accelerator-control-system-design-presentation": 1,
    "shine-accelerator-preliminary-design-report-2017": 3
  },
  "examples": [
    {
      "chunk_id": "epics-application-developers-guide-r3-16-2:83952420e3325ba044ceac4be733ac659d90591227e5934991a794f1eb9c9ee1",
      "document_id": "epics-application-developers-guide-r3-16-2",
      "page": 2,
      "text": "2",
      "eligible": false,
      "reasons": [
        "number_or_running_code_only"
      ],
      "effective_characters": 1,
      "effective_tokens": 1,
      "replacement_ratio": 0.0
    },
    {
      "chunk_id": "shine-accelerator-control-system-design-presentation:3bbcf79edceead55ba4ebb0cc291b2f6f3a4243f699a87b882fa5d02566647b4",
      "document_id": "shine-accelerator-control-system-design-presentation",
      "page": 34,
      "text": "谢 谢",
      "eligible": false,
      "reasons": [
        "boilerplate_only"
      ],
      "effective_characters": 2,
      "effective_tokens": 2,
      "replacement_ratio": 0.0
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:2119956386059a9909003e07de59e3a5401a2bb3b6f29432d66c690cd54e776b",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "page": 308,
      "text": "图3.3.6.1-30 束流倾角入射示意图\n\n对整个腔体长度进行积分，得到束流倾角入射时在腔体内激发的信号如下所\n\n示：\n\n��= A\n\n−�\n\n2\n\n� 2 ����� න �−\n\n�+ � �����\n\n2� �����+ � �����\n\n��\n\n�\n\n=\n\n�����\n\n� �−\n\n�\n\n2� −�\n\n2\n\n� 2 � ׬ �−\n\n� �����\n\n2� ��������\n\n��\n\n�����+ ��������\n\n��\n\n����� dz\n\n当条件2   时，即腔体谐振信号周期远小于衰减时间常数时，积分项内当z\n\n从-L/2 到L/2，�\n\n�\n\n−�����\n\n2�项结果均近似为1，因此可简化成：\n\n��≈\n\n�����\n\n� �−\n\n�\n\n2� −�\n\n2\n\n� 2 � ׬ ��������\n\n��\n\n����� dz\n\n= �����\n\n� �−�\n\n2������ 2�2���2� �2 ��� �� 2�����−������ � ��� �� 2�����\n\n由此可知，当束流倾角从腔体中心入射时，激励信号的相位与位置偏移信号\n\n在相位上相差90°，令 p v v  即为倾角为θ时的等效束流偏移量，仿真结果如\n\n图3.3.6.1-31 所示：",
      "eligible": false,
      "reasons": [
        "mostly_replacement_chars"
      ],
      "effective_characters": 195,
      "effective_tokens": 184,
      "replacement_ratio": 0.40389294403892945
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:9f2ae54d8aa5a8d641ea3cc6ca033c924a41bde166fe3c6b20ef8ebbff264dea",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "page": 310,
      "text": "��= A �−������−�\n\n2�������� �\n\n图3.3.6.1-33 束流倾角入射示意图\n\n对整个腔体长度L 进行积分，得到：\n\n��= A\n\n−�\n\n2\n\n� 2 ����� න �−\n\n�+ � �����\n\n2� �����+ � �����\n\n��\n\n�\n\n= �����\n\n� �−�\n\n2������ 2�2���2� �2 ��� �� 2�����−������ � ��� �� 2�����\n\n−�����\n\n�\n\n2����� � ��� �� 2������−� 2������\n\n从公式中可知此种情况下分解成了两部分，第一部分和公式（7）相同，等\n\n效成束流按倾角θ经过腔体中心的结果。第二项对比公式（4），可等效看成在经\n\n过腔体过程中偏离电中心距离为：\n\n�= �����\n\n�\n\n2����� � ��� �� 2�����\n\n当腔体参数以及倾角θ确定时，等效偏移量与m 成正比，第一项、第二项\n\n的影响分别如图3.3.6.1-34、3.3.6.1-35 所示，两项和的影响如图3.3.6.1-36 所示：",
      "eligible": false,
      "reasons": [
        "mostly_replacement_chars"
      ],
      "effective_characters": 190,
      "effective_tokens": 175,
      "replacement_ratio": 0.38917525773195877
    },
    {
      "chunk_id": "shine-accelerator-preliminary-design-report-2017:f82b231d3421be698e7f2b56a0199e8a7bedc5d6db1f664bda04d9d1abb0d3ee",
      "document_id": "shine-accelerator-preliminary-design-report-2017",
      "page": 312,
      "text": "倾角带来的影响。模型可如图3.3.6.1-37 所示并假设束团呈高斯分布：\n\n图3.3.6.1-37 束团自身倾角入射模型\n\n设束团长度为 z ，束团电荷量为q ，束团自身倾角为，等效结果可视为\n\n将束团分割成一组组带电量为dq 的电子沿z 轴分布，则每组电子的位置偏移量\n\n为�tan �假设束团呈高斯分布，则有：\n\n��= q\n\n2π�� �\n\n−�2\n\n2��2��\n\n结合此前公式，则有：\n\n���= ω\n\n2 � ����\n\n( �\n\n�)0�\n\n−�2��2\n\n�2 �tan (�)\n\n�0\n\n�−�\n\n2�sin ωt ��\n\n= �tan (�)\n\n2��� ��\n\n−�2\n\n2��2�−� 2�sin ωt ��\n\n积分得：\n\n��= �tan (�)\n\n2��� −∞\n\n+∞\n\n��\n\n−�2\n\n2��2�− �−�\n\n� 2� sin ω �−�\n\n� �� න\n\n= �tan (�)\n\n2��� �−�\n\n2�\n\n−��\n\n+��\n\n��\n\n−�2\n\n2��2�−� 2��sin ω �−� � �� න\n\n≈�ωσ�\n\n2����\n\n2��� �−�\n\n2������\n\n由此可知，当束团自身存在倾角时，激励信号的相位与位置偏移信号在相位\n\n上也相差90°，令 p v v  即束团倾角为α时的等效束流偏移量，仿真结果如图\n\n3.3.6.1-38 所示：",
      "eligible": false,
      "reasons": [
        "mostly_replacement_chars"
      ],
      "effective_characters": 273,
      "effective_tokens": 233,
      "replacement_ratio": 0.25164113785557984
    }
  ]
}
```


## 人工核对与执行验证

页眉残留为正文合并情况。公式损坏与未解释的 PUA 继续保留。资格阈值和原始异常事实分别记录。

```json
{
  "repeated_header_case": {
    "document_id": "shine-accelerator-preliminary-design-report-2017",
    "signature": "硬X射线自由电子激光装置初步设计报告——加速器分册",
    "raw_pages": 470,
    "stage_two_retained_pages": 470,
    "stage_two_five_remaining_chunks": 9,
    "remaining": [
      {
        "chunk_id": "shine-accelerator-preliminary-design-report-2017:263efa1463c8458f946ee77130a00801cb8a3fda99320f934f48d4a7d18af575",
        "page": 142
      },
      {
        "chunk_id": "shine-accelerator-preliminary-design-report-2017:b426e41e69608130b9380634cf8795a01c2b141c079d579e8ee0ff846232344f",
        "page": 143
      },
      {
        "chunk_id": "shine-accelerator-preliminary-design-report-2017:564c4f599876573d43395476bfeffe0b3284efc55de30f03de19658b625d33c0",
        "page": 144
      },
      {
        "chunk_id": "shine-accelerator-preliminary-design-report-2017:800e4532e5a98a17de2ffa8f1dd89a2f7e71e47f81b4774295f1833ac174f964",
        "page": 145
      },
      {
        "chunk_id": "shine-accelerator-preliminary-design-report-2017:b8e1af474039fb239bdcf21430cd49327aa9407d21f3efb72684d725983b84de",
        "page": 146
      },
      {
        "chunk_id": "shine-accelerator-preliminary-design-report-2017:5a83362ea4fc3d2fc123fd24f98a8f75938ac999a37404dfc34f3f0d0732d488",
        "page": 147
      },
      {
        "chunk_id": "shine-accelerator-preliminary-design-report-2017:58eddfa38b3bdaa408479227b66a041489e249d4de2ef1d950a7a9e84c8d344b",
        "page": 148
      },
      {
        "chunk_id": "shine-accelerator-preliminary-design-report-2017:87044a3ec4d2df453eb74f75a2270bd9943faa6ee2050f940c5b20cec9aaa891",
        "page": 149
      },
      {
        "chunk_id": "shine-accelerator-preliminary-design-report-2017:836befeacf6b3db50c04e6d67e3a0593f8604e6f273628286482372620d0c21a",
        "page": 371
      }
    ],
    "limitation": "Remaining headers are merged with body text; no file-specific deletion added.",
    "stage_two_index_header_chunk_count": 470,
    "historical_point_count": 4547
  },
  "replacement_policy_evidence": {
    "top_nonwhitespace_ratios": [
      0.40389294403892945,
      0.38917525773195877,
      0.25164113785557984
    ],
    "next_ratio": 0.08695652173913043,
    "threshold": 0.2,
    "minimum_replacements": 8,
    "note": "Threshold lies in observed ratio gap; boundary tests 19/20/21 percent preserve the lower-damage body. Not a retrieval score threshold."
  },
  "remaining_limits": [
    "376 eligible inputs still exceed 512 tokens; 300/528 Chinese chunks are affected. No claim that tokenizer truncation is the sole cause of Dense failures.",
    "Directory dot leaders remain eligible and dominate maximum token examples; meaningful Chinese body also exceeds the limit.",
    "9 combined header/body chunks still retain the reviewed running header.",
    "U+FFFD and unexplained PUA remain in the corpus; formulas are not reconstructed.",
    "21 answerable judgments are seeded and nonexhaustive; slice counts are diagnostic only. Hard negatives cover a narrow temporal/live-state family."
  ]
}
```

```json
{
  "point_count": 4532,
  "eligible_chunks": 4532,
  "duplicate_count": 0,
  "payload_citations_and_uuid_and_vector_dimension_norm_checked": true,
  "per_document_points": {
    "epics-documentation-latest-2026-08-18": 1071,
    "shine-accelerator-preliminary-design-report-2017": 477,
    "european-xfel-full-technical-design-report-2007": 1730,
    "epics-application-developers-guide-r3-16-2": 847,
    "european-xfel-undulator-commissioning-spectrometer-cdr-2011": 41,
    "shine-cryogenic-control-system-2021": 22,
    "shine-accelerator-fast-interlock-2024": 18,
    "european-xfel-x-ray-optics-beam-transport-tdr-2012": 235,
    "shine-epics-ioc-pv-information-management-pcapac2022": 13,
    "shine-accelerator-control-system-design-presentation": 33,
    "shine-white-rabbit-beam-synchronous-timing-ipac2022": 17,
    "shine-control-system-status-icalepcs2019": 15,
    "european-xfel-standard-e-beam-diagnostics-linac2010": 13
  },
  "historical_point_count": 4547,
  "first_and_final_real_index_count_equal": true,
  "protected_source_and_agent_files": 22,
  "protected_hashes_unchanged": true,
  "code_and_frozen_query_hashes_match_measurement": true,
  "commands": {
    "pytest -q": {
      "exit_code": 0,
      "stdout": "........................................................................ [ 46%]\n........................................................................ [ 93%]\n..........                                                               [100%]\n154 passed in 2.55s\n",
      "stderr": ""
    },
    "ruff check .": {
      "exit_code": 0,
      "stdout": "All checks passed!\n",
      "stderr": ""
    },
    "git diff --check": {
      "exit_code": 0,
      "stdout": "",
      "stderr": ""
    },
    "python scripts/corpus_inventory.py": {
      "exit_code": 0,
      "stdout": "Registered documents\n01. data/l0_raw/EPICS/EPICS_Application_Developers_Guide_R3.16.2.pdf | control_system/epics | en | R3.16.2 (2018-10-22) | active\n02. data/l0_raw/EPICS/EPICS_Documentation_latest.pdf | control_system/epics | en | latest (2026-08-18) | active\n03. data/l0_raw/Hard_XFEL_European_XFEL/European_XFEL_Full_Technical_Design_Report.pdf | accelerator_physics/accelerator_design | en | DESY 2006-097 (2007-07) | reference\n04. data/l0_raw/Hard_XFEL_European_XFEL/European_XFEL_Undulator_Commissioning_Spectrometer_CDR.pdf | beam_diagnostics/photon_diagnostics | en | Rev B, Ver 2 (2011-06-08) | reference\n05. data/l0_raw/Hard_XFEL_European_XFEL/European_XFEL_X-Ray_Optics_and_Beam_Transport_TDR.pdf | accelerator_physics/beam_transport | en | XFEL.EU TR-2012-006 (2012-12) | reference\n06. data/l0_raw/Hard_XFEL_European_XFEL/Standard_E-Beam_Diagnostics_for_European_XFEL.pdf | beam_diagnostics/electron_beam_diagnostics | en | LINAC2010 TUP095 | reference\n07. data/l0_raw/Hard_XFEL_SHINE/EPICS_IOC_and_PVs_Information_Management_System_for_SHINE_PCaPAC2022.pdf | control_system/ioc | en | PCaPAC2022 FRO21 | reference\n08. data/l0_raw/Hard_XFEL_SHINE/SHINE_Accelerator_Fast_Interlock_System_Design_and_Development_CN.pdf | control_system/interlock | zh | 核技术 47(12):120203 (2024-12) | reference\n09. data/l0_raw/Hard_XFEL_SHINE/Status_of_the_SHINE_Control_System_ICALEPCS2019.pdf | control_system/control_architecture | en | ICALEPCS2019 WEPHA167 | reference\n10. data/l0_raw/Hard_XFEL_SHINE/The_Cryogenic_Control_System_of_SHINE_2021.pdf | control_system/cryogenics | en | EPJ Techniques and Instrumentation (2021) | reference\n11. data/l0_raw/Hard_XFEL_SHINE/White_Rabbit_Based_Beam_Synchronous_Timing_Systems_for_SHINE_IPAC2022.pdf | control_system/timing | en | IPAC2022 THIYGD1 | reference\n12. data/l0_raw/SHINE加速器控制系统设计与开发.pdf | control_system/control_architecture | zh | unknown | reference\n13. data/l0_raw/加速器分册(20171226).pdf | accelerator_physics/accelerator_design | zh | 初步设计报告 (2017-12-26) | reference\n\nCorpus inventory\nregistered_documents: 13\nregistered_pdfs: 13\nraw_files: 18\nunsupported_unmanaged_source_files: 5\nregistered_size: 69.7 MiB\ncategories: accelerator_physics=3, beam_diagnostics=2, control_system=8\ntopics: accelerator_design=2, beam_transport=1, control_architecture=2, cryogenics=1, electron_beam_diagnostics=1, epics=2, interlock=1, ioc=1, photon_diagnostics=1, timing=1\ndocument_types: pdf=13\nlanguages: en=10, zh=3\nstatuses: active=2, reference=11\nunsupported_unmanaged_sources (outside PDF validation):\n  - data/l0_raw/control_system/EPICS_7_Overview.pptx\n  - data/l0_raw/control_system/EPICS_Centos8_Packages.docx\n  - data/l0_raw/control_system/EPICS_IOC_Setup.pptx\n  - data/l0_raw/control_system/LNL_Accelerator_Complex_Code_Legend_Rule.docx\n  - data/l0_raw/control_system/areaDetector_training.pptx\nvalidation: OK\n",
      "stderr": ""
    }
  }
}
```
