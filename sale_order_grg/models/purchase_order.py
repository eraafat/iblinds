from odoo import fields, models, api


class PurchaseOrderLine(models.Model):
    _inherit = 'purchase.order.line'

    height = fields.Float()
    width = fields.Float()
    count = fields.Integer()

    @api.onchange('height', 'width', 'count')
    def onchange_eight_width(self):
        print("purchase height and width")
        if self.width and self.height:
            self.product_qty = self.width * self.height * self.count

    def _prepare_stock_move_vals(self, picking, price_unit, product_uom_qty, product_uom):
        self.ensure_one()
        self._check_orderpoint_picking_type()
        product = self.product_id.with_context(lang=self.order_id.dest_address_id.lang or self.env.user.lang)
        date_planned = self.date_planned or self.order_id.date_planned
        return {
            # truncate to 2000 to avoid triggering index limit error
            # TODO: remove index in master?
            'name': (self.product_id.display_name or '')[:2000],
            'product_id': self.product_id.id,
            'date': date_planned,
            'date_deadline': date_planned,
            'location_id': self.order_id.partner_id.property_stock_supplier.id,
            'location_dest_id': (self.orderpoint_id and not (
                        self.move_ids | self.move_dest_ids)) and self.orderpoint_id.location_id.id or self.order_id._get_destination_location(),
            'picking_id': picking.id,
            'partner_id': self.order_id.dest_address_id.id,
            'move_dest_ids': [(4, x) for x in self.move_dest_ids.ids],
            'state': 'draft',
            'purchase_line_id': self.id,
            'company_id': self.order_id.company_id.id,
            'price_unit': price_unit,
            'picking_type_id': self.order_id.picking_type_id.id,
            'group_id': self.order_id.group_id.id,
            'origin': self.order_id.name,
            'description_picking': product.description_pickingin or self.name,
            'propagate_cancel': self.propagate_cancel,
            'warehouse_id': self.order_id.picking_type_id.warehouse_id.id,
            'product_uom_qty': product_uom_qty,
            'product_uom': product_uom.id,
            'width': self.width,
            'height': self.height,
            'count': self.count,
            'product_packaging_id': self.product_packaging_id.id,
            'sequence': self.sequence,
        }
    def _prepare_account_move_line(self, move=False):
        self.ensure_one()
        aml_currency = move and move.currency_id or self.currency_id
        date = move and move.date or fields.Date.today()

        res = {
            'display_type': self.display_type or 'product',
            'name': self.env['account.move.line']._get_journal_items_full_name(self.name, self.product_id.display_name),
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom.id,
            'quantity': self.qty_to_invoice,
            'discount': self.discount,
            'price_unit': self.currency_id._convert(self.price_unit, aml_currency, self.company_id, date, round=False),
            'tax_ids': [(6, 0, self.taxes_id.ids)],
            'purchase_line_id': self.id,
            'count': self.count,
            'width': self.width,
            'height': self.height,
            'is_downpayment': self.is_downpayment,
        }
        if self.analytic_distribution and not self.display_type:
            res['analytic_distribution'] = self.analytic_distribution
        return res