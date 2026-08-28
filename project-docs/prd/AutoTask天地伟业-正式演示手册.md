# AutoTask天地伟业-正式演示手册

```
准备清空测试数据：
1、客户订单: .\.venv\Scripts\python.exe scripts\clear_process_instances.py --yes POJS2607170008
2、对账单：.\.venv\Scripts\python.exe scripts\clear_statement_bills.py --yes
```

## 一、客户订单

  系统定时扫单(待签章)客户订单，自动生成SDMS销售订单，无需员工触发。
  本次演示没有待回签，选择客户订单号：POJS2607170008，已回签的数据作为演练。

#### 1.1 扫单

```
AutoTask 会通过定时器，查询待签章客户订单，然后自动创建sdms销售订单草稿单。(可以手动扫单=手动触发）

sdms销售订单编辑---审批  (不在我们 AutoTask 系统)
```

#### 1.2 填写交货日期

```
    操作：选择交货日期，保存。演示这里用脚本 执行：
    .\.venv\Scripts\python.exe scripts\simulate_fill_delivery_dates.py --yes --date 2026-08-21 POJS2607170008
    执行完成后  行状态是【已写入】
```



#### 1.2 发起签章申请

```
  操作：点击【去签章】按钮。演示这里用脚本模拟 执行：
  .\.venv\Scripts\python.exe scripts\reset_to_sign_requested.py --yes POJS2607170008
  执行完成后 SOP节点是【待回签】
```



#### 1.3 扫描已回签下载签章合同上传sdms销售订单

```
 操作：AutoTask 系统定时器触发，无需人工操作。(立即回签轮询=手动人工触发)

 操作完成，SOP节点进入【完成】，链条结束。
```



## 二、客户对账单



#### 2.1 创建对账单&核验双方对账单

```
前提条件：sdms创建对账单（校验标准：客户子代码 + 业务实体编号 + 本月创建 + 对账金额一致）
操作：【生成客户对账单】--入库确认期间--搜索--勾选行数据--【生成对账单】
生成对账单前会校验双方对账单数据，校验标准上面。不通过无法生成。
注意：本次演示不是真的在SRM系统生成，只做演示。
```



#### 2.2 未对账对账单-上传发票-提交审核

```
本次演示上面创建的对账单SRM实际是没有生成，所以需要脚本生成一个未对账未上传的对账单。
执行：.\.venv\Scripts\python.exe scripts\seed_official_unchecked_statement.py --yes --check-date 2026-04-01 --check-amount 5768205.32
操作：【选择发票】--【扫描发票】--人工核对发票--【提交审核】
注意：本次演练提交审核只是AutoTask提交 SRM系统不操作。

模拟提交审核脚本执行：
.\.venv\Scripts\python.exe scripts\simulate_stmt_submit_review.py --yes --check-date 2026-04-01 --check-amount 5768205.32
```



## 三、业务反馈问题清单

1、生成销售订单有消息提醒；

2、销售订单审批完成才可以去填写交期-签章(填写前校验)；

3、发票扫描-可以解密 再去扫描；