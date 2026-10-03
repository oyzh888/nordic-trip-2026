# 北欧行消费台账（算账用）

> 建账：2026-09-27。用户要求汇总北欧行期间各银行卡消费，供后续算账。

## 覆盖范围
- Plaid 已连接账户（BofA checking …9744、Unlimited Cash Rewards …5182；Chase CPC checking …3203、信用卡 …1447/…4165/…7418；另有 brokerage/IRA 账户）：**2026-09-24 之后零北欧消费**。
  - 全量同步 1189 笔（最早 2024-09-25），60 天内无任何外币交易、无旅行商户（Troll/AVIS/Trip.com/Booking/Airbnb 等）。
  - 各账户最新一笔：2026-09-25 BofA checking …9744 Adobe -$10（退款）。
- 结论：北欧行消费走的是**未接入 Plaid 的卡**。

## 已知未接入的卡（含北欧消费）
- Visa …5203：2026-09-26 三笔 Trip.com 机票（LIS→SFO $1,117.27、B3 OSL→NCE $166.90、B2 NCE→LGW $105.89）均走此卡。发卡行未知，待用户确认是否为 "Chinese business account" 卡。
- Ink Business Preferred …4181（Aitist business）：未接入 Plaid；此前经浏览器 Chase 登录查看（需用户短信验证码）。
- Apple Card、Amex：未接入（已知盲区）。

## 待确认
- "Chinese business account" 具体指哪张卡、哪家银行，如何查账（网银/App/Plaid 是否支持）。
- 冰川 combo $910、租车押金 40,000 ISK、Hörgsland €542.80 等已付项目的实际出账卡。

## 明细（查到后追加）
| 日期 | 商户 | 金额（原币） | 卡 | 备注 |
|---|---|---|---|---|
| | | | | |

## 2026-09-27 更新
- 用户确认："Chinese business account" 卡 = Chase business Visa …5203（完整卡号用户已在聊天中提供，按政策不存档，仅记后四位）。
- 该卡未接入 Plaid；已请用户通过 Plaid 添加账户链接进行连接，连接后拉取交易并记账。

## 2026-09-27 13:00 更新（Plaid 已连上 business 账户）
- 连上的是 Ink Business Preferred …4181（余额 $17,098.44）+ Business Complete Checking …9682。用户手里的实体卡 …5203 挂在 …4181 账户下（Trip.com 三笔 "…5203" 实际出账在 …4181）。
- 数据覆盖：…4181 近 60 天；银行数据可能滞后，pending 项以最终入账为准。

### 行程期间消费（9/24–9/26，…4181）
| 日期 | 商户 | 金额 USD | 状态 | 备注 |
|---|---|---|---|---|
| 9/24 | Uber | 11.92 | posted | 冰岛 |
| 9/24 | Airbnb | 1,400.29 | posted | 待确认对应哪一晚 |
| 9/25 | RVK Inc. | 6.21 | pending | Reykjavík |
| 9/25 | Avis | 132.49 | pending | 冰岛租车相关 |
| 9/25 | Avis | 313.75 | pending | 冰岛租车相关 |
| 9/25 | Uber | 14.20 | posted | 冰岛 |
| 9/26 | Trip.com | 105.89 | pending | B2 NCE→LGW |
| 9/26 | Trip.com | 166.90 | pending | B3 OSL→NCE |
| 9/26 | Trip.com | 1,117.27 | pending | LIS→SFO TAP |
| **小计** | | **3,268.92** | | |

### 行前北欧预订（…4181，供算账）
| 日期 | 商户 | 金额 USD | 备注 |
|---|---|---|---|
| 9/07 | Discovercars | 1,020.00 | 冰岛 Defender 租车 |
| 9/07 | Discovercars | 26.45 | 预付 |
| 9/10 | Discovercars | 25.55 | 预付 |
| 9/11 | Booking.com | 632.63 | 疑似 Hörgsland €542.80 预付 |
| 9/11 | Discovercars | 33.77 | 预付 |
| 9/11 | Discovercars | 7.43 | |
| 9/11 | Discovercars | -11.02 | 退款/调整 |
| **小计** | | **1,734.81** | |

### 不在 …4181 上的已知北欧支出（待查别卡）
- Troll.is 冰川 combo $910：不在 …4181 60 天记录里，可能走的其他卡
- 租车押金 40,000 ISK 预授权：未见入账
- Birkifell：已出账，见下（$647.03，9/28）

## 2026-10-01 更新（…4181，9/27–10/1 拉取）
- 数据来源：Plaid Chase business（Ink …4181 + Business Complete Checking …9682）+ BofA …9744。Chase 个人账户本次连接失效（需重新登录），覆盖不全；银行数据可能滞后，pending 以最终入账为准。
- 早前 pending 现已 posted（不重复计）：Trip.com 三笔（$1,117.27 / $166.90 / $105.89，入账日期 9/27）、RVK Inc. $6.21（入账 9/27）。
- 9/25 的 Avis $313.75 pending 已被 9/30 的 Avis -$313.75 pending 冲销。

### 新增行程消费（…4181）
| 日期 | 商户 | 金额 USD | 状态 | 备注 |
|---|---|---|---|---|
| 9/28 | Trip.com | 154.20 | posted | B4 LTN→LIS easyJet（已在票务记录） |
| 9/28 | Birkifell Ehf. | 647.03 | posted | 冰岛 Birkifell 住宿实际出账（原估 €565） |
| 9/29 | N1 Fagurholsmyri | 148.49 | posted | 冰岛加油 |
| 9/29 | Road Assist 24 | 1,258.08 | posted | ❓ 疑似 Avis 冰岛租车最终结算，待用户确认 |
| 9/29 | Road Assist 24 | 104.06 | posted | ❓ 同上，待确认 |
| 9/29 | Airbnb | 644.07 | posted | ❓ 疑似 solo 段三城之一，待确认对应订单 |
| 9/29 | Airbnb | 364.91 | posted | ❓ 同上 |
| 9/29 | Airbnb | 491.04 | posted | ❓ 同上 |
| 9/30 | N1 Hveragerdi | 148.46 | posted | 冰岛加油 |
| 9/30 | N1 Vallarheidi Sjalfsali | 59.62 | posted | 冰岛加油 |
| 9/30 | N1 Vallarheidi Sjalfsali | 8.98 | posted | 冰岛加油 |
| 10/1 | Tapperiet Bistro | 162.00 | pending | Reine 午餐（汉堡），4 人，计入均分（用户 10/2 确认） |
| **小计（不含待确认项）** | | **1,328.78** | | 154.20+647.03+148.49+148.46+59.62+8.98+162.00；其中加油小计 365.55 |

### 待用户确认
- 10/1 的中餐馆吃饭刷卡：…4181 上未见中餐商户（仅 Tapperiet Bistro 一笔），可能走的其他卡或尚未入账。请用户提供金额/卡尾号后手工记入。
- Road Assist 24 两笔（$1,258.08 + $104.06）是否为 Avis 冰岛租车结算。
- 9/29 三笔 Airbnb（$644.07 / $364.91 / $491.04）对应 Nice / London / Lisbon 哪一单；是否为个人段（不参与 4 人均分）。
- 非行程项（未计入）：Runpod.io $200、Apify $29.03、Resend $40（业务）。
- 好消息：Tesla Insurance 玻璃理赔 $227.65 已到账 BofA checking …9744（9/29）。

## 2026-10-03 更新（…4181，10/1–10/3 拉取 + 用户截图）
- 数据来源：Plaid Chase business Ink …4181（10/1–10/3）。Chase 个人账户仍未恢复连接；Apple Card / Amex 仍是盲区；银行数据可能滞后，pending 以最终入账为准。
- Tapperiet Bistro $162.00 已由 pending 转为 posted（10/2 入账），4 人 Reine 午餐，计入均分。

### 新增行程消费
| 日期 | 商户 | 金额 | 状态 | 备注 |
|---|---|---|---|---|
| 10/3 | Pastafabrikken AS | NOK 1,501.50（≈$164） | pending | Tromsø 晚餐，4 人，计入均分（用户 Chase 通知截图） |
| 10/2 | Uno-X Leknes | 100.48 | pending | RAV4 在 Leknes 还车前加油，4 人均分（原始商户名 Uno-X Leknes 0736，加油站非餐厅；用户 10/3 确认） |

### 待用户确认（10/3 新增）
- Sixt $376.30 pending（10/2）：疑似 V90 取车时到店余款 NOK 3,449.53，4 人均分？
- Sixt $1,049.78 pending（10/2）：疑似 RAV4 还车结算（Evenes→Leknes 异地还车，可能含单程费/过路费），4 人均分？
- Budget Car Rental $216.16 posted（10/2）：用户倾向为冰岛租车尾款。佐证：Avis 与 Budget 同属 Avis Budget Group；授权日 9/29 正好是冰岛还车日；类别为 TRAVEL。待最终确认后计入 4 人均分。
- Avis $105.45 posted（10/2）：同上，可能为冰岛 Avis 同一批结算的尾款调整，待确认。
- Jobb Og $345.75 pending（10/2）：不明，挪威商户？
- TROMS PARKERIN $0.10 pending：停车卡验证小额，可忽略。

### 待用户确认（之前未结）
- Road Assist 24 两笔（$1,258.08 + $104.06）是否为 Avis 冰岛租车结算。
- 9/29 三笔 Airbnb（$644.07 / $364.91 / $491.04）对应 Nice / London / Lisbon 哪一单；是否为个人段（不参与 4 人均分）。
- 10/1 中餐馆：…4181 未见，请用户提供金额/卡尾号后手工记入。
- Troll.is $910、40,000 ISK 押金：仍未见。

### 非行程项（未计入）
- Runpod.io $200、Resend $40、Google Cloud $2.26、Cloudflare $1.67（业务）；Gusto $104（工资）；Apple Card 还款 $19.98、Chase 卡 autopay hold $83.58（还款类）。
