# Supplier Portal Prepare ERP Order Draft

This Flow logs in through the Engine-managed browser, opens a customer purchase
order, downloads the portal-provided XLSX attachment, and prepares an ERP draft.
It does not call or transmit data to an ERP endpoint.

ERP draft rules:

1. The page is used only to navigate to the requested order and initiate the
   download. No displayed page field is copied into the ERP request body.
2. The XLSX attachment supplies every mapped source field.
3. `customerName` defaults to `天地偉業技術有限公司`, `orderType` defaults to
   `常规订单`, `orderedDate` is the China business date at execution time,
   `taxRate` defaults to `0.13`, and `isAttachment` is `Y`.
4. Fields marked for automatic interface/EBS matching remain empty.
5. `comments` reads only the XLSX `备注` column; `直发备注` is retained in the
   parsed attachment detail but is not mapped to the ERP body.
6. The attachment order number must match the requested `po_no`.

The only Flow input is `po_no`. The Flow contains no ERP HTTP client and performs
no transmission.

The current Engine Runtime ignores a Flow function return value. Local tests can
inspect the returned draft, but production delivery requires a governed
structured-result channel before an ERP push stage is added.
