from odoo import fields, models, api, _
from odoo.exceptions import ValidationError

from odoo.tools import float_compare

class ProductPricelist(models.Model):
    _inherit = 'product.pricelist'

    not_change_price = fields.Boolean()


class SaleOrder(models.Model):
    _inherit = 'sale.order'

    delivery_date_from = fields.Date(required=True)
    delivery_date_to = fields.Date()
    mrp_sent = fields.Boolean()
    purchase_sent = fields.Boolean()
    manufacture_to_other = fields.Boolean(compute='calc_if_manufacture_to_other')
    employee_id = fields.Many2one('hr.employee', "Previewer")

    customer_source_id = fields.Many2one('customer.source', 'Source', related='partner_id.customer_source_id',
                                         index=True, ondelete='set null')
    color_id = fields.Many2one('product.product', domain="[('is_fabric','=',True)]")
    product_id = fields.Many2one('product.product', domain="[('sale_ok','=',True)]")
    discount_for_lines = fields.Float(string='Discount')
    unit_price = fields.Float()
    partner_category_id = fields.Many2one('res.partner.category',compute='get_partner_category_from_customer',store=True,
                                            string='Partner tags')

    def _create_invoices(self, grouped=False, final=False, date=None):
        """Link timesheets to the created invoices. Date interval is injected in the
        context in sale_make_invoice_advance_inv wizard.
        """
        # print(self)
        moves =  super(SaleOrder, self)._create_invoices(grouped=grouped, final=final, date=date)
        if self.employee_id   :
            # print(self.employee_id.id)
            moves.reviewer_employee_id = self.employee_id.id
        return moves

    @api.depends('partner_id')
    def get_partner_category_from_customer(self):
        for rec in self:
            if rec.partner_id.category_id:
                rec.partner_category_id = rec.partner_id.category_id[0]

    def apply_discount_for_lines(self):
        for line in self.order_line:
            if  not line.display_type:
                line.discount = self.discount_for_lines
                line.price_unit = self.unit_price

    total_counts = fields.Integer(compute='calculate_count_of_lines', store=True)
    total_quantity = fields.Float(compute='calculate_count_of_lines', store=True)

    @api.depends('order_line', 'order_line.count')
    def calculate_count_of_lines(self):
        for rec in self:
            total_count = 0
            total_qunatity = 0
            rec.total_counts = 0
            rec.total_quantity =0
            for line in rec.order_line:
                if line.count and not line.display_type and line.width and line.height:
                    total_count += line.count
                    total_qunatity += line.product_uom_qty
            rec.total_counts = total_count
            rec.total_quantity = round(total_qunatity,2)

    @api.depends('order_line')
    def calc_if_manufacture_to_other(self):
        for rec in self:
            manuf = False
            for line in rec.order_line:
                if line.product_id.manufacture_to_other:
                    manuf = True
                    rec.manufacture_to_other = True
                else:
                    rec.manufacture_to_other = manuf
            rec.manufacture_to_other = manuf

    def create_purchase_order(self):
        purchase_order = self.env['purchase.order']
        for line in self.order_line:
            vendor = line.product_id.seller_ids.mapped('name')
            if not vendor:
                raise ValidationError("Please Add Vendor for {}".format(line.product_id.name))

            if line.product_id.manufacture_to_other == True:
                if not purchase_order:
                    purchase_order = self.env['purchase.order'].create({
                        # 'partner_id':line.product_id.seller_ids.mapped(lambda r: r.name == self.partner_a)
                        'partner_id': line.product_id.seller_ids.mapped('name')[0].id
                    })
                    print('purchase_order', purchase_order)
                # if not line.purchase_sent:
                #     order_lines = {'product_id': line.product_id.id, 'name': line.name + '[' + line.color_id.name + ']',
                #                    'count': line.count, 'width': line.width,
                #                    'height': line.height, 'product_qty': line.product_uom_qty}
                #     purchase_order.order_line = [(0, 0, order_lines)]
                #     print(order_lines)
                #     line.purchase_sent = True
        self.purchase_sent = True
        # purchase_line = self.env['purchase.order.line'].create(order_lines)
        # line.purchase_line_ids = purchase_line.id

    # mrp_request_id = fields.Many2one('mrp.request')

    def view_mrp_request_action(self):
        request = self.env['mrp.request'].search([('sales_order_number', '=', self.name)])
        action = self.env["ir.actions.actions"]._for_xml_id("sale_order_grg.action_mrp_request_form")
        if len(request) == 1:
            form_view = [(self.env.ref('sale_order_grg.view_mrp_request_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = request.id
        elif len(request) > 1:
            tree_view = [(self.env.ref('sale_order_grg.view_mrp_request_tree').id, 'tree')]
            if 'views' in action:
                action['views'] = tree_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = tree_view
            action['domain'] = [('sales_order_number', '=', self.name)]
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def view_purchase_request_action(self):
        request = self.env['purchase.order'].search([('sales_order_number', '=', self.name)])
        action = self.env["ir.actions.actions"]._for_xml_id("sale_order_grg.action_mrp_request_form")
        if request:
            form_view = [(self.env.ref('sale_order_grg.view_mrp_request_form').id, 'form')]
            if 'views' in action:
                action['views'] = form_view + [(state, view) for state, view in action['views'] if view != 'form']
            else:
                action['views'] = form_view
            action['res_id'] = request.id
        else:
            action = {'type': 'ir.actions.act_window_close'}
        return action

    def send_to_manufacturing(self):
        mrp_line_vals = []
        mrp_request = self.env['mrp.request'].create({
            'sales_order_number': self.name,
            'partner_id': self.partner_id.id,
            'delivery_date': self.delivery_date_from
        })
        for line in self.order_line:
            if line.product_id and line.color_id and line.product_id.bom_count > 0:
                line.create_bom_for_line()
                values = {
                    'product_id': line.product_id.id,
                    'color_id': line.color_id.id,
                    'height': line.height,
                    'width': line.width,
                    'count': line.count,
                    'bom_id': line.bom_id.id,
                }
                print('so_vals')
                print(line.bom_id)
                mrp_line_vals.append(values)
                mrp_request.order_line = [(0, 0, values)]
        self.mrp_sent = True


class SaleOrderLine(models.Model):
    _inherit = 'sale.order.line'

    height = fields.Float()
    width = fields.Float()
    count = fields.Integer(default=1)
    purchase_sent = fields.Boolean()
    color_id = fields.Many2one('product.product')
    
    mrp_state = fields.Selection([('draft', 'draft'), ('MRP', 'MRP')], default='draft')
    send_to_mrp = fields.Boolean()
    bom_count = fields.Integer(related='product_id.bom_count')
    bom_id = fields.Many2one('mrp.bom', groups='mrp.group_mrp_user')
    note = fields.Char('Note')




    @api.depends('product_type', 'product_uom_qty', 'qty_delivered', 'state', 'move_ids', 'product_uom')
    def _compute_qty_to_deliver(self):
        """Compute the visibility of the inventory widget."""
        for line in self:
            if not line.count > 0:
                line.qty_to_deliver = line.product_uom_qty - line.qty_delivered
            else:
                line.qty_to_deliver = line.count - line.qty_delivered
            if line.state in ('draft', 'sent',
                              'sale') and line.product_type == 'product' and line.product_uom and line.qty_to_deliver > 0:
                if line.state == 'sale' and not line.move_ids:
                    line.display_qty_widget = False
                else:
                    line.display_qty_widget = True
            else:
                line.display_qty_widget = False

    # def _action_launch_stock_rule(self, previous_product_uom_qty=False):
    #     """
    #     Launch procurement group run method with required/custom fields genrated by a
    #     sale order line. procurement group will launch '_run_pull', '_run_buy' or '_run_manufacture'
    #     depending on the sale order line product rule.
    #     """
    #     if self._context.get("skip_procurement"):
    #         return True
    #     precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
    #     procurements = []
    #     for line in self:
    #         line = line.with_company(line.company_id)
    #         if line.state != 'sale' or not line.product_id.type in ('consu', 'product'):
    #             continue
    #         qty = line._get_qty_procurement(previous_product_uom_qty)
    #         if not line.count > 0:
    #             if float_compare(qty, line.product_uom_qty, precision_digits=precision) == 0:
    #                 continue
    #         else:
    #             if float_compare(qty, line.count, precision_digits=precision) == 0:
    #                 continue
    #
    #         group_id = line._get_procurement_group()
    #         if not group_id:
    #             group_id = self.env['procurement.group'].create(line._prepare_procurement_group_vals())
    #             line.order_id.procurement_group_id = group_id
    #         else:
    #             # In case the procurement group is already created and the order was
    #             # cancelled, we need to update certain values of the group.
    #             updated_vals = {}
    #             if group_id.partner_id != line.order_id.partner_shipping_id:
    #                 updated_vals.update({'partner_id': line.order_id.partner_shipping_id.id})
    #             if group_id.move_type != line.order_id.picking_policy:
    #                 updated_vals.update({'move_type': line.order_id.picking_policy})
    #             if updated_vals:
    #                 group_id.write(updated_vals)
    #
    #         values = line._prepare_procurement_values(group_id=group_id)
    #         if not line.count > 0 or line.product_id.manufacture_to_other:
    #             product_qty = line.product_uom_qty - qty
    #         elif not line.product_id.manufacture_to_other:
    #             product_qty = line.count - qty
    #         line_uom = line.product_uom
    #         quant_uom = line.product_id.uom_id
    #         product_qty, procurement_uom = line_uom._adjust_uom_quantities(product_qty, quant_uom)
    #         procurements.append(self.env['procurement.group'].Procurement(
    #             line.product_id, product_qty, procurement_uom,
    #             line.order_id.partner_shipping_id.property_stock_customer,
    #             line.product_id.display_name, line.order_id.name, line.order_id.company_id, values, line.width,
    #             line.height, line.count))
    #         print(procurements)
    #     if procurements:
    #         self.env['procurement.group'].run(procurements)

    @api.onchange('height', 'width', 'count')
    def onchange_eight_width(self):
        print("iam in height and width")
        if self.width and self.height:
            limit = self.order_id.partner_id.category_id.min_quantity
            unit_quantity = self.width * self.height
            print('unit_quantity')
            print(unit_quantity)
            self.product_uom_qty = unit_quantity * self.count if unit_quantity > limit else limit * self.count

    def create_bom_for_line(self):
        bom_obj = self.env['mrp.bom'].search(
            ['|', ('product_tmpl_id', '=', self.product_id.product_tmpl_id.id), ('product_id', '=', self.product_id.id),
             ('type', '=', 'normal'), ('is_standard', '=', True)])
        if len(bom_obj) > 1:
            raise ValidationError(_(" It must be one BOM"))
        if not bom_obj:
            raise ValidationError(_("Please add bom for {}".format(self.product_id.name)))
        print(bom_obj)
        if bom_obj:
            bom_id = self.env['mrp.bom'].create(
                {
                    'product_id': bom_obj.product_id.id,
                    'product_tmpl_id': bom_obj.product_tmpl_id.id,
                    'product_qty': 1,
                    'partner_id': self.order_id.partner_id.id,
                    'sale_order_number': self.order_id.name,
                    'code': self.order_id.name + ' - ' + self.order_id.partner_id.name,
                    'sale_order_line_id': self.id,
                    'is_standard': False,
                }
            )
            for line in bom_obj.bom_line_ids:
                qty = 1
                if line.qty_type == 'width':
                    qty = self.width * (100 + line.extra_percentage) / 100
                elif line.qty_type == 'height':
                    qty = self.height * (100 + line.extra_percentage) / 100
                elif line.qty_type == 'width_height':
                    qty = self.width * self.height * (100 + line.extra_percentage) / 100
                elif line.qty_type == 'unit':
                    qty = 1

                values = {
                    'product_id': line.product_id.id if not line.product_id.is_fabric else self.color_id.id,
                    'product_qty': qty,
                    'qty_type': line.qty_type,
                    'extra_percentage': line.extra_percentage,
                    'bom_id': bom_id.id

                }
                self.env['mrp.bom.line'].create(values)
            print('bom_id')
            print(bom_id)
            self.bom_id = bom_id.id
            print(self.bom_id)

    def _prepare_invoice_line(self, **optional_values):
        """
        Prepare the dict of values to create the new invoice line for a sales order line.

        :param qty: float quantity to invoice
        :param optional_values: any parameter that should be added to the returned invoice line
        """
        self.ensure_one()
        res = {
            'display_type': self.display_type,
            'sequence': self.sequence,
            'name': self.name,
            'color_id': self.color_id.id,
            'count': self.count,
            'width': self.width,
            'height': self.height,
            'product_id': self.product_id.id,
            'product_uom_id': self.product_uom.id,
            'quantity': self.qty_to_invoice,
            'discount': self.discount,
            'price_unit': self.price_unit,
            'tax_ids': [(6, 0, self.tax_id.ids)],
            'sale_line_ids': [(4, self.id)],
        } if not self.display_type else {'display_type': self.display_type,
            'sequence': self.sequence,
            'name': self.name,
            'color_id': False,
            'count': 0,
            'width': 0,
            'height': 0,
            'product_id': False,
            'product_uom_id':False,
            'quantity': 0,
            'discount': 0,
            'price_unit':0,
            'sale_line_ids': [(4, self.id)],}
        if self.order_id.analytic_account_id and not self.display_type:
            res['analytic_account_id'] = self.order_id.analytic_account_id.id
        if self.analytic_tag_ids and not self.display_type:
            res['analytic_tag_ids'] = [(6, 0, self.analytic_tag_ids.ids)]
        if optional_values:
            res.update(optional_values)
        if self.display_type:
            res['account_id'] = False
        return res

    @api.depends('product_id', 'color_id','product_uom', 'product_uom_qty')
    def _compute_pricelist_item_id(self):
        for line in self:
            if not line.product_id or line.display_type or not line.order_id.pricelist_id:
                line.pricelist_item_id = False
            else:
                product_id = line.color_id if line.color_id else line.product_id
                print(product_id)
                line.pricelist_item_id = line.order_id.pricelist_id._get_product_rule(
                    product_id,
                    quantity=line.product_uom_qty or 1.0,
                    uom=line.product_uom,
                    date=line._get_order_date(),
                )
    def _get_pricelist_price(self):
        """Compute the price given by the pricelist for the given line information.

        :return: the product sales price in the order currency (without taxes)
        :rtype: float
        """
        self.ensure_one()
        self.product_id.ensure_one()
        product_id = self.color_id if self.color_id else self.product_id
        # if self.order_id.pricelist_id.not_change_price:
        #     return self.price_unit
        price = self.pricelist_item_id._compute_price(
            product=product_id.with_context(**self._get_product_price_context()),
            quantity=self.product_uom_qty or 1.0,
            uom=self.product_uom,
            date=self._get_order_date(),
            currency=self.currency_id,
        )
        return price

    # @api.onchange('product_uom', 'product_uom_qty','color_id')
    # def product_uom_change(self):
    #     if not self.product_uom or not self.product_id:
    #         self.price_unit = 0.0
    #         return
    #     if self.order_id.pricelist_id and self.order_id.partner_id:
    #         product_id = self.color_id if self.color_id else self.product_id
    #         product = product_id.with_context(
    #             lang=self.order_id.partner_id.lang,
    #             partner=self.order_id.partner_id,
    #             quantity=self.product_uom_qty,
    #             date=self.order_id.date_order,
    #             pricelist=self.order_id.pricelist_id.id,
    #             uom=self.product_uom.id,
    #             fiscal_position=self.env.context.get('fiscal_position')
    #         )
    #         self.price_unit = product._get_tax_included_unit_price(
    #             self.company_id or self.order_id.company_id,
    #             self.order_id.currency_id,
    #             self.order_id.date_order,
    #             'sale',
    #             fiscal_position=self.order_id.fiscal_position_id,
    #             product_price_unit=self._get_display_price(product),
    #             product_currency=self.order_id.currency_id
    #         )


class ProductTemplate(models.Model):
    _inherit = 'product.template'

    is_fabric = fields.Boolean()
    manufacture_to_other = fields.Boolean()
