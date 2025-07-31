import logging

from odoo import _, api, fields, models
from odoo.exceptions import UserError
from odoo.osv import expression
from odoo.tools import OrderedSet
from odoo.tools.float_utils import float_compare, float_is_zero, float_round
from psycopg2 import Error
from odoo.exceptions import ValidationError


_logger = logging.getLogger(__name__)


class StockQuant(models.Model):
    _inherit = 'stock.quant'

    height = fields.Float()
    width = fields.Float()
    count = fields.Float(compute="compute_count_of_product")

    @api.model
    def _get_inventory_fields_create(self):
        """ Returns a list of fields user can edit when he want to create a quant in `inventory_mode`.
        """
        return ['product_id', 'location_id', 'lot_id', 'package_id', 'owner_id', 'count', 'width',
                'height'] + self._get_inventory_fields_write()

    #
    # @api.model
    # def _merge_quants(self):
    #     """ In a situation where one transaction is updating a quant via
    #     `_update_available_quantity` and another concurrent one calls this function with the same
    #     argument, we’ll create a new quant in order for these transactions to not rollback. This
    #     method will find and deduplicate these quants.
    #     """
    #     print('_merge_quants-------------------')
    #     query = """WITH
    #                     dupes AS (
    #                         SELECT min(id) as to_update_quant_id,
    #                             (array_agg(id ORDER BY id))[2:array_length(array_agg(id), 1)] as to_delete_quant_ids,
    #                             SUM(reserved_quantity) as reserved_quantity,
    #                             SUM(inventory_quantity) as inventory_quantity,
    #                             SUM(quantity) as quantity,
    #                             MIN(in_date) as in_date
    #                         FROM stock_quant
    #                         GROUP BY product_id, company_id, location_id, lot_id, width,height,package_id, owner_id
    #                         HAVING count(id) > 1
    #                     ),
    #                     _up AS (
    #                         UPDATE stock_quant q
    #                             SET quantity = d.quantity,
    #                                 reserved_quantity = d.reserved_quantity,
    #                                 inventory_quantity = d.inventory_quantity,
    #                                 in_date = d.in_date
    #                         FROM dupes d
    #                         WHERE d.to_update_quant_id = q.id
    #                     )
    #                DELETE FROM stock_quant WHERE id in (SELECT unnest(to_delete_quant_ids) from dupes)
    #     """
    #     try:
    #         with self.env.cr.savepoint():
    #             self.env.cr.execute(query)
    #             # self.invalidate_cache()
    #     except Error as e:
    #         _logger.info('an error occurred while merging quants: %s', e.pgerror)

    # @api.constrains('quantity')
    # def check_quantity(self):
    #     for quant in self:
    #         if quant.location_id.usage != 'inventory' and quant.lot_id and quant.product_id.tracking == 'serial' \
    #                 and float_compare(abs(quant.quantity), 1, precision_rounding=quant.product_uom_id.rounding) > 0:
    #             raise ValidationError(
    #                 _('The serial number has already been assigned: \n Product: %s, Serial Number: %s') % (
    #                 quant.product_id.display_name, quant.lot_id.name))

    @api.depends('width', 'height', 'inventory_quantity_auto_apply')
    def compute_count_of_product(self):
        for rec in self:
            if rec.height and rec.width:
                print('inventory_quantity_set')
                print(rec.inventory_quantity_auto_apply)
                count = 0
                if rec.inventory_quantity_auto_apply:
                    count = rec.inventory_quantity_auto_apply / (rec.height * rec.width)
                elif rec.inventory_quantity:
                    count = rec.inventory_quantity / (rec.height * rec.width)

                print(count)
                if count < 1:
                    height = rec.inventory_quantity_auto_apply / rec.width
                    print(height)
                    if height:
                        rec.write({'height': height})
                    # rec.compute_count_of_product()
                rec.count = count
            else:
                rec.count = 0

    # @api.model
    # def _get_inventory_fields_write(self):
    #     """ Returns a list of fields user can edit when he want to edit a quant in `inventory_mode`.
    #     """
    #     fields = ['inventory_quantity', 'inventory_quantity_auto_apply', 'inventory_diff_quantity', 'count', 'width','accounting_date',
    #               'height', 'inventory_date', 'user_id', 'inventory_quantity_set', 'is_outdated']
    #     print('fields',fields)
    #     return fields

    # def _gather(self, product_id, location_id, lot_id=None, package_id=None, owner_id=None, strict=False, width=0,
    #             height=0):
    #     removal_strategy = self._get_removal_strategy(product_id, location_id)
    #     removal_strategy_order = self._get_removal_strategy_order(removal_strategy)
    #
    #     domain = [('product_id', '=', product_id.id)]
    #     if not strict:
    #         if lot_id:
    #             domain = expression.AND([['|', ('lot_id', '=', lot_id.id), ('lot_id', '=', False)], domain])
    #         if package_id:
    #             domain = expression.AND([[('package_id', '=', package_id.id)], domain])
    #         if owner_id:
    #             domain = expression.AND([[('owner_id', '=', owner_id.id)], domain])
    #         if width:
    #             domain = expression.AND([[('width', '=', width)], domain])
    #         if height:
    #             domain = expression.AND([[('height', '=', height)], domain])
    #         domain = expression.AND([[('location_id', 'child_of', location_id.id)], domain])
    #     else:
    #         domain = expression.AND(
    #             [['|', ('lot_id', '=', lot_id.id), ('lot_id', '=', False)] if lot_id else [('lot_id', '=', False)],
    #              domain])
    #         domain = expression.AND([[('package_id', '=', package_id and package_id.id or False)], domain])
    #         domain = expression.AND([[('owner_id', '=', owner_id and owner_id.id or False)], domain])
    #         domain = expression.AND([[('location_id', '=', location_id.id)], domain])
    #
    #     return self.search(domain, order=removal_strategy_order).sorted(lambda q: not q.lot_id)
    #
    # @api.model
    # def _update_available_quantity(self, product_id, location_id, quantity, lot_id=None, package_id=None, owner_id=None,
    #                                in_date=None, width=0, height=0):
    #     """ Increase or decrease `reserved_quantity` of a set of quants for a given set of
    #     product_id/location_id/lot_id/package_id/owner_id.
    #
    #     :param product_id:
    #     :param location_id:
    #     :param quantity:
    #     :param lot_id:
    #     :param package_id:
    #     :param owner_id:
    #     :param datetime in_date: Should only be passed when calls to this method are done in
    #                              order to move a quant. When creating a tracked quant, the
    #                              current datetime will be used.
    #     :return: tuple (available_quantity, in_date as a datetime)
    #     """
    #     self = self.sudo()
    #     quants = self._gather(product_id, location_id, lot_id=lot_id, package_id=package_id, owner_id=owner_id,
    #                           strict=True, width=width, height=height)
    #     if lot_id and quantity > 0:
    #         quants = quants.filtered(lambda q: q.lot_id)
    #     if width and height:
    #         quants = quants.filtered(lambda q: q.width == width and q.height == height)
    #
    #     if location_id.should_bypass_reservation():
    #         incoming_dates = []
    #     else:
    #         incoming_dates = [quant.in_date for quant in quants if quant.in_date and
    #                           float_compare(quant.quantity, 0, precision_rounding=quant.product_uom_id.rounding) > 0]
    #     if in_date:
    #         incoming_dates += [in_date]
    #     # If multiple incoming dates are available for a given lot_id/package_id/owner_id, we
    #     # consider only the oldest one as being relevant.
    #     if incoming_dates:
    #         in_date = min(incoming_dates)
    #     else:
    #         in_date = fields.Datetime.now()
    #
    #     quant = None
    #     if quants:
    #         # see _acquire_one_job for explanations
    #         self._cr.execute(
    #             "SELECT id FROM stock_quant WHERE id IN %s ORDER BY lot_id LIMIT 1 FOR NO KEY UPDATE SKIP LOCKED",
    #             [tuple(quants.ids)])
    #         stock_quant_result = self._cr.fetchone()
    #         if stock_quant_result:
    #             quant = self.browse(stock_quant_result[0])
    #
    #     if quant:
    #         quant.write({
    #             'quantity': quant.quantity + quantity,
    #             'in_date': in_date,
    #         })
    #     else:
    #         valuess = {
    #             'product_id': product_id.id,
    #             'location_id': location_id.id,
    #             'quantity': quantity,
    #             'lot_id': lot_id and lot_id.id,
    #             'height': height,
    #             'width': width,
    #             'package_id': package_id and package_id.id,
    #             'owner_id': owner_id and owner_id.id,
    #             'in_date': in_date,
    #         }
    #         print("valuess")
    #         print(valuess)
    #         self.create(valuess)
    #     return self._get_available_quantity(product_id, location_id, lot_id=lot_id, package_id=package_id,
    #                                         owner_id=owner_id, strict=False, allow_negative=True), in_date
    #

class StockMove(models.Model):
    _inherit = 'stock.move'

    width = fields.Float("Width")
    height = fields.Float("Height")
    count = fields.Integer("Count")

    # def _prepare_move_line_vals(self, quantity=None, reserved_quant=None):
    #     self.ensure_one()
    #     vals = {
    #         'move_id': self.id,
    #         'product_id': self.product_id.id,
    #         'product_uom_id': self.product_uom.id,
    #         'location_id': self.location_id.id,
    #         'location_dest_id': self.location_dest_id.id,
    #         'picking_id': self.picking_id.id,
    #         'company_id': self.company_id.id,
    #         'width': self.width,
    #         'height': self.height,
    #         'count': self.count,
    #     }
    #     if quantity:
    #         rounding = self.env['decimal.precision'].precision_get('Product Unit of Measure')
    #         uom_quantity = self.product_id.uom_id._compute_quantity(quantity, self.product_uom,
    #                                                                 rounding_method='HALF-UP')
    #         uom_quantity = float_round(uom_quantity, precision_digits=rounding)
    #         uom_quantity_back_to_product_uom = self.product_uom._compute_quantity(uom_quantity, self.product_id.uom_id,
    #                                                                               rounding_method='HALF-UP')
    #         if float_compare(quantity, uom_quantity_back_to_product_uom, precision_digits=rounding) == 0:
    #             vals = dict(vals, product_uom_qty=uom_quantity)
    #         else:
    #             vals = dict(vals, product_uom_qty=quantity, product_uom_id=self.product_id.uom_id.id)
    #     package = None
    #     if reserved_quant:
    #         package = reserved_quant.package_id
    #         vals = dict(
    #             vals,
    #             location_id=reserved_quant.location_id.id,
    #             lot_id=reserved_quant.lot_id.id or False,
    #             package_id=package.id or False,
    #             owner_id=reserved_quant.owner_id.id or False,
    #         )
    #     return vals


class StockMoveLine(models.Model):
    _inherit = 'stock.move.line'

    height = fields.Float()
    width = fields.Float()
    count = fields.Integer()

    @api.onchange('count', 'width', 'height')
    def compute_done_quantity(self):
        if self.count and self.width and self.height:
            self.qty_done = self.count * self.width * self.height

    # def write(self, vals):
    #     if self.env.context.get('bypass_reservation_update'):
    #         return super(StockMoveLine, self).write(vals)
    #
    #     if 'product_id' in vals and any(
    #             vals.get('state', ml.state) != 'draft' and vals['product_id'] != ml.product_id.id for ml in self):
    #         raise UserError(_("Changing the product is only allowed in 'Draft' state."))
    #
    #     moves_to_recompute_state = self.env['stock.move']
    #     Quant = self.env['stock.quant']
    #     precision = self.env['decimal.precision'].precision_get('Product Unit of Measure')
    #     triggers = [
    #         ('location_id', 'stock.location'),
    #         ('location_dest_id', 'stock.location'),
    #         ('lot_id', 'stock.production.lot'),
    #         ('package_id', 'stock.quant.package'),
    #         ('result_package_id', 'stock.quant.package'),
    #         ('owner_id', 'res.partner'),
    #         ('product_uom_id', 'uom.uom')
    #     ]
    #     updates = {}
    #     for key, model in triggers:
    #         if key in vals:
    #             updates[key] = self.env[model].browse(vals[key])
    #
    #     if 'result_package_id' in updates:
    #         for ml in self.filtered(lambda ml: ml.package_level_id):
    #             if updates.get('result_package_id'):
    #                 ml.package_level_id.package_id = updates.get('result_package_id')
    #             else:
    #                 # TODO: make package levels less of a pain and fix this
    #                 package_level = ml.package_level_id
    #                 ml.package_level_id = False
    #                 # Only need to unlink the package level if it's empty. Otherwise will unlink it to still valid move lines.
    #                 if not package_level.move_line_ids:
    #                     package_level.unlink()
    #
    #     # When we try to write on a reserved move line any fields from `triggers` or directly
    #     # `product_uom_qty` (the actual reserved quantity), we need to make sure the associated
    #     # quants are correctly updated in order to not make them out of sync (i.e. the sum of the
    #     # move lines `product_uom_qty` should always be equal to the sum of `reserved_quantity` on
    #     # the quants). If the new charateristics are not available on the quants, we chose to
    #     # reserve the maximum possible.
    #     if updates or 'product_uom_qty' in vals:
    #         for ml in self.filtered(
    #                 lambda ml: ml.state in ['partially_available', 'assigned'] and ml.product_id.type == 'product'):
    #
    #             if 'product_uom_qty' in vals:
    #                 new_product_uom_qty = ml.product_uom_id._compute_quantity(
    #                     vals['product_uom_qty'], ml.product_id.uom_id, rounding_method='HALF-UP')
    #                 # Make sure `product_uom_qty` is not negative.
    #                 if float_compare(new_product_uom_qty, 0, precision_rounding=ml.product_id.uom_id.rounding) < 0:
    #                     raise UserError(_('Reserving a negative quantity is not allowed.'))
    #             else:
    #                 new_product_uom_qty = ml.product_qty
    #
    #             # Unreserve the old charateristics of the move line.
    #             if not ml.move_id._should_bypass_reservation(ml.location_id):
    #                 Quant._update_reserved_quantity(ml.product_id, ml.location_id, -ml.product_qty, lot_id=ml.lot_id,
    #                                                 package_id=ml.package_id, owner_id=ml.owner_id, strict=True)
    #
    #             # Reserve the maximum available of the new charateristics of the move line.
    #             if not ml.move_id._should_bypass_reservation(updates.get('location_id', ml.location_id)):
    #                 reserved_qty = 0
    #                 try:
    #                     q = Quant._update_reserved_quantity(ml.product_id, updates.get('location_id', ml.location_id),
    #                                                         new_product_uom_qty,
    #                                                         lot_id=updates.get('lot_id', ml.lot_id),
    #                                                         package_id=updates.get('package_id', ml.package_id),
    #                                                         owner_id=updates.get('owner_id', ml.owner_id), strict=True)
    #                     reserved_qty = sum([x[1] for x in q])
    #                 except UserError:
    #                     pass
    #                 if reserved_qty != new_product_uom_qty:
    #                     new_product_uom_qty = ml.product_id.uom_id._compute_quantity(reserved_qty, ml.product_uom_id,
    #                                                                                  rounding_method='HALF-UP')
    #                     moves_to_recompute_state |= ml.move_id
    #                     ml.with_context(bypass_reservation_update=True).product_uom_qty = new_product_uom_qty
    #                     # we don't want to override the new reserved quantity
    #                     vals.pop('product_uom_qty', None)
    #
    #     # When editing a done move line, the reserved availability of a potential chained move is impacted. Take care of running again `_action_assign` on the concerned moves.
    #     if updates or 'qty_done' in vals:
    #         next_moves = self.env['stock.move']
    #         mls = self.filtered(lambda ml: ml.move_id.state == 'done' and ml.product_id.type == 'product')
    #         if not updates:  # we can skip those where qty_done is already good up to UoM rounding
    #             mls = mls.filtered(lambda ml: not float_is_zero(ml.qty_done - vals['qty_done'],
    #                                                             precision_rounding=ml.product_uom_id.rounding))
    #         for ml in mls:
    #             # undo the original move line
    #             qty_done_orig = ml.product_uom_id._compute_quantity(ml.qty_done, ml.move_id.product_id.uom_id,
    #                                                                 rounding_method='HALF-UP')
    #             in_date = \
    #                 Quant._update_available_quantity(ml.product_id, ml.location_dest_id, -qty_done_orig,
    #                                                  lot_id=ml.lot_id,
    #                                                  package_id=ml.result_package_id, owner_id=ml.owner_id,
    #                                                  width=ml.width,
    #                                                  height=ml.height)[1]
    #             Quant._update_available_quantity(ml.product_id, ml.location_id, qty_done_orig, lot_id=ml.lot_id,
    #                                              package_id=ml.package_id, owner_id=ml.owner_id, in_date=in_date,
    #                                              width=ml.width, height=ml.height)
    #
    #             # move what's been actually done
    #             product_id = ml.product_id
    #             location_id = updates.get('location_id', ml.location_id)
    #             location_dest_id = updates.get('location_dest_id', ml.location_dest_id)
    #             qty_done = vals.get('qty_done', ml.qty_done)
    #             lot_id = updates.get('lot_id', ml.lot_id)
    #             package_id = updates.get('package_id', ml.package_id)
    #             result_package_id = updates.get('result_package_id', ml.result_package_id)
    #             owner_id = updates.get('owner_id', ml.owner_id)
    #             product_uom_id = updates.get('product_uom_id', ml.product_uom_id)
    #             quantity = product_uom_id._compute_quantity(qty_done, ml.move_id.product_id.uom_id,
    #                                                         rounding_method='HALF-UP')
    #             if not ml.move_id._should_bypass_reservation(location_id):
    #                 ml._free_reservation(product_id, location_id, quantity, lot_id=lot_id, package_id=package_id,
    #                                      owner_id=owner_id)
    #             if not float_is_zero(quantity, precision_digits=precision):
    #                 print(ml.width)
    #                 print(ml.height)
    #                 available_qty, in_date = Quant._update_available_quantity(product_id, location_id, -quantity,
    #                                                                           lot_id=lot_id, package_id=package_id,
    #                                                                           owner_id=owner_id, width=ml.width,
    #                                                                           height=ml.height)
    #                 if available_qty < 0 and lot_id:
    #                     # see if we can compensate the negative quants with some untracked quants
    #                     untracked_qty = Quant._get_available_quantity(product_id, location_id, lot_id=False,
    #                                                                   package_id=package_id, owner_id=owner_id,
    #                                                                   strict=True)
    #                     if untracked_qty:
    #                         taken_from_untracked_qty = min(untracked_qty, abs(available_qty))
    #                         Quant._update_available_quantity(product_id, location_id, -taken_from_untracked_qty,
    #                                                          lot_id=False, package_id=package_id, owner_id=owner_id,
    #                                                          width=ml.width, height=ml.height)
    #                         Quant._update_available_quantity(product_id, location_id, taken_from_untracked_qty,
    #                                                          lot_id=lot_id, package_id=package_id, owner_id=owner_id,
    #                                                          width=ml.width, height=ml.height)
    #                         if not ml.move_id._should_bypass_reservation(location_id):
    #                             ml._free_reservation(ml.product_id, location_id, untracked_qty, lot_id=False,
    #                                                  package_id=package_id, owner_id=owner_id)
    #                 Quant._update_available_quantity(product_id, location_dest_id, quantity, lot_id=lot_id,
    #                                                  package_id=result_package_id, owner_id=owner_id, in_date=in_date,
    #                                                  width=ml.width, height=ml.height)
    #
    #             # Unreserve and reserve following move in order to have the real reserved quantity on move_line.
    #             next_moves |= ml.move_id.move_dest_ids.filtered(lambda move: move.state not in ('done', 'cancel'))
    #
    #             # Log a note
    #             if ml.picking_id:
    #                 ml._log_message(ml.picking_id, ml, 'stock.track_move_template', vals)
    #
    #     res = super(StockMoveLine, self).write(vals)
    #
    #     # Update scrap object linked to move_lines to the new quantity.
    #     if 'qty_done' in vals:
    #         for move in self.mapped('move_id'):
    #             if move.scrapped:
    #                 move.scrap_ids.write({'scrap_qty': move.quantity_done})
    #
    #     # As stock_account values according to a move's `product_uom_qty`, we consider that any
    #     # done stock move should have its `quantity_done` equals to its `product_uom_qty`, and
    #     # this is what move's `action_done` will do. So, we replicate the behavior here.
    #     if updates or 'qty_done' in vals:
    #         moves = self.filtered(lambda ml: ml.move_id.state == 'done').mapped('move_id')
    #         moves |= self.filtered(lambda ml: ml.move_id.state not in (
    #             'done', 'cancel') and ml.move_id.picking_id.immediate_transfer and not ml.product_uom_qty).mapped(
    #             'move_id')
    #         for move in moves:
    #             move.product_uom_qty = move.quantity_done
    #         next_moves._do_unreserve()
    #         next_moves._action_assign()
    #
    #     if moves_to_recompute_state:
    #         moves_to_recompute_state._recompute_state()
    #
    #     return res

    # @api.model_create_multi
    # def create(self, vals_list):
    #     for vals in vals_list:
    #         if vals.get('move_id'):
    #             vals['company_id'] = self.env['stock.move'].browse(vals['move_id']).company_id.id
    #         elif vals.get('picking_id'):
    #             vals['company_id'] = self.env['stock.picking'].browse(vals['picking_id']).company_id.id
    #         if self.env.context.get('import_file') and vals.get('product_uom_qty'):
    #             raise UserError(
    #                 _("It is not allowed to import reserved quantity, you have to use the quantity directly."))
    #
    #     mls = super().create(vals_list)
    #
    #     def create_move(move_line):
    #         new_move = self.env['stock.move'].create(move_line._prepare_stock_move_vals())
    #         move_line.move_id = new_move.id
    #
    #     # If the move line is directly create on the picking view.
    #     # If this picking is already done we should generate an
    #     # associated done move.
    #     for move_line in mls:
    #         if move_line.move_id or not move_line.picking_id:
    #             continue
    #         if move_line.picking_id.state != 'done':
    #             moves = move_line.picking_id.move_lines.filtered(lambda x: x.product_id == move_line.product_id)
    #             moves = sorted(moves, key=lambda m: m.quantity_done < m.product_qty, reverse=True)
    #             if moves:
    #                 move_line.move_id = moves[0].id
    #             else:
    #                 create_move(move_line)
    #         else:
    #             create_move(move_line)
    #
    #     moves_to_update = mls.filtered(
    #         lambda ml:
    #         ml.move_id and
    #         ml.qty_done and (
    #                 ml.move_id.state == 'done' or (
    #                 ml.move_id.picking_id and
    #                 ml.move_id.picking_id.immediate_transfer
    #         ))
    #     ).move_id
    #     for move in moves_to_update:
    #         move.with_context(avoid_putaway_rules=True).product_uom_qty = move.quantity_done
    #
    #     for ml, vals in zip(mls, vals_list):
    #         if ml.state == 'done':
    #             if ml.product_id.type == 'product':
    #                 Quant = self.env['stock.quant']
    #                 quantity = ml.product_uom_id._compute_quantity(ml.qty_done, ml.move_id.product_id.uom_id,
    #                                                                rounding_method='HALF-UP')
    #                 in_date = None
    #                 available_qty, in_date = Quant._update_available_quantity(ml.product_id, ml.location_id, -quantity,
    #                                                                           lot_id=ml.lot_id,
    #                                                                           package_id=ml.package_id,
    #                                                                           owner_id=ml.owner_id)
    #                 if available_qty < 0 and ml.lot_id:
    #                     # see if we can compensate the negative quants with some untracked quants
    #                     untracked_qty = Quant._get_available_quantity(ml.product_id, ml.location_id, lot_id=False,
    #                                                                   package_id=ml.package_id, owner_id=ml.owner_id,
    #                                                                   strict=True)
    #                     if untracked_qty:
    #                         taken_from_untracked_qty = min(untracked_qty, abs(quantity))
    #                         Quant._update_available_quantity(ml.product_id, ml.location_id, -taken_from_untracked_qty,
    #                                                          lot_id=False, package_id=ml.package_id,
    #                                                          owner_id=ml.owner_id, width=ml.width, height=ml.height)
    #                         Quant._update_available_quantity(ml.product_id, ml.location_id, taken_from_untracked_qty,
    #                                                          lot_id=ml.lot_id, package_id=ml.package_id,
    #                                                          owner_id=ml.owner_id, width=ml.width, height=ml.height)
    #                 Quant._update_available_quantity(ml.product_id, ml.location_dest_id, quantity, lot_id=ml.lot_id,
    #                                                  package_id=ml.result_package_id, owner_id=ml.owner_id,
    #                                                  in_date=in_date, width=ml.width, height=ml.height)
    #             next_moves = ml.move_id.move_dest_ids.filtered(lambda move: move.state not in ('done', 'cancel'))
    #             next_moves._do_unreserve()
    #             next_moves._action_assign()
    #     return mls

    # def _action_done(self):
    #     """ This method is called during a move's `action_done`. It'll actually move a quant from
    #     the source location to the destination location, and unreserve if needed in the source
    #     location.
    #
    #     This method is intended to be called on all the move lines of a move. This method is not
    #     intended to be called when editing a `done` move (that's what the override of `write` here
    #     is done.
    #     """
    #     Quant = self.env['stock.quant']
    #
    #     # First, we loop over all the move lines to do a preliminary check: `qty_done` should not
    #     # be negative and, according to the presence of a picking type or a linked inventory
    #     # adjustment, enforce some rules on the `lot_id` field. If `qty_done` is null, we unlink
    #     # the line. It is mandatory in order to free the reservation and correctly apply
    #     # `action_done` on the next move lines.
    #     ml_ids_tracked_without_lot = OrderedSet()
    #     ml_ids_to_delete = OrderedSet()
    #     ml_ids_to_create_lot = OrderedSet()
    #     for ml in self:
    #         # Check here if `ml.qty_done` respects the rounding of `ml.product_uom_id`.
    #         uom_qty = float_round(ml.qty_done, precision_rounding=ml.product_uom_id.rounding, rounding_method='HALF-UP')
    #         precision_digits = self.env['decimal.precision'].precision_get('Product Unit of Measure')
    #         qty_done = float_round(ml.qty_done, precision_digits=precision_digits, rounding_method='HALF-UP')
    #         if float_compare(uom_qty, qty_done, precision_digits=precision_digits) != 0:
    #             raise UserError(_('The quantity done for the product "%s" doesn\'t respect the rounding precision '
    #                               'defined on the unit of measure "%s". Please change the quantity done or the '
    #                               'rounding precision of your unit of measure.') % (
    #                                 ml.product_id.display_name, ml.product_uom_id.name))
    #
    #         qty_done_float_compared = float_compare(ml.qty_done, 0, precision_rounding=ml.product_uom_id.rounding)
    #         if qty_done_float_compared > 0:
    #             if ml.product_id.tracking != 'none':
    #                 picking_type_id = ml.move_id.picking_type_id
    #                 if picking_type_id:
    #                     if picking_type_id.use_create_lots:
    #                         # If a picking type is linked, we may have to create a production lot on
    #                         # the fly before assigning it to the move line if the user checked both
    #                         # `use_create_lots` and `use_existing_lots`.
    #                         if ml.lot_name and not ml.lot_id:
    #                             lot = self.env['stock.production.lot'].search([
    #                                 ('company_id', '=', ml.company_id.id),
    #                                 ('product_id', '=', ml.product_id.id),
    #                                 ('name', '=', ml.lot_name),
    #                             ], limit=1)
    #                             if lot:
    #                                 ml.lot_id = lot.id
    #                             else:
    #                                 ml_ids_to_create_lot.add(ml.id)
    #                     elif not picking_type_id.use_create_lots and not picking_type_id.use_existing_lots:
    #                         # If the user disabled both `use_create_lots` and `use_existing_lots`
    #                         # checkboxes on the picking type, he's allowed to enter tracked
    #                         # products without a `lot_id`.
    #                         continue
    #                 elif ml.is_inventory:
    #                     # If an inventory adjustment is linked, the user is allowed to enter
    #                     # tracked products without a `lot_id`.
    #                     continue
    #
    #                 if not ml.lot_id and ml.id not in ml_ids_to_create_lot:
    #                     ml_ids_tracked_without_lot.add(ml.id)
    #         elif qty_done_float_compared < 0:
    #             raise UserError(_('No negative quantities allowed'))
    #         elif not ml.is_inventory:
    #             ml_ids_to_delete.add(ml.id)
    #
    #     if ml_ids_tracked_without_lot:
    #         mls_tracked_without_lot = self.env['stock.move.line'].browse(ml_ids_tracked_without_lot)
    #         raise UserError(_('You need to supply a Lot/Serial Number for product: \n - ') +
    #                         '\n - '.join(mls_tracked_without_lot.mapped('product_id.display_name')))
    #     ml_to_create_lot = self.env['stock.move.line'].browse(ml_ids_to_create_lot)
    #     ml_to_create_lot.with_context(bypass_reservation_update=True)._create_and_assign_production_lot()
    #
    #     mls_to_delete = self.env['stock.move.line'].browse(ml_ids_to_delete)
    #     mls_to_delete.unlink()
    #
    #     mls_todo = (self - mls_to_delete)
    #     mls_todo._check_company()
    #
    #     # Now, we can actually move the quant.
    #     ml_ids_to_ignore = OrderedSet()
    #     for ml in mls_todo:
    #         if ml.product_id.type == 'product':
    #             rounding = ml.product_uom_id.rounding
    #
    #             # if this move line is force assigned, unreserve elsewhere if needed
    #             if not ml.move_id._should_bypass_reservation(ml.location_id) and float_compare(ml.qty_done,
    #                                                                                            ml.product_uom_qty,
    #                                                                                            precision_rounding=rounding) > 0:
    #                 qty_done_product_uom = ml.product_uom_id._compute_quantity(ml.qty_done, ml.product_id.uom_id,
    #                                                                            rounding_method='HALF-UP')
    #                 extra_qty = qty_done_product_uom - ml.product_qty
    #                 ml._free_reservation(ml.product_id, ml.location_id, extra_qty, lot_id=ml.lot_id,
    #                                      package_id=ml.package_id, owner_id=ml.owner_id,
    #                                      ml_ids_to_ignore=ml_ids_to_ignore)
    #             # unreserve what's been reserved
    #             if not ml.move_id._should_bypass_reservation(
    #                     ml.location_id) and ml.product_id.type == 'product' and ml.product_qty:
    #                 Quant._update_reserved_quantity(ml.product_id, ml.location_id, -ml.product_qty, lot_id=ml.lot_id,
    #                                                 package_id=ml.package_id, owner_id=ml.owner_id, strict=True)
    #
    #             # move what's been actually done
    #             quantity = ml.product_uom_id._compute_quantity(ml.qty_done, ml.move_id.product_id.uom_id,
    #                                                            rounding_method='HALF-UP')
    #             available_qty, in_date = Quant._update_available_quantity(ml.product_id, ml.location_id, -quantity,
    #                                                                       lot_id=ml.lot_id, package_id=ml.package_id,
    #                                                                       owner_id=ml.owner_id, width=ml.width,
    #                                                                       height=ml.height)
    #             if available_qty < 0 and ml.lot_id:
    #                 # see if we can compensate the negative quants with some untracked quants
    #                 untracked_qty = Quant._get_available_quantity(ml.product_id, ml.location_id, lot_id=False,
    #                                                               package_id=ml.package_id, owner_id=ml.owner_id,
    #                                                               strict=True)
    #                 if untracked_qty:
    #                     taken_from_untracked_qty = min(untracked_qty, abs(quantity))
    #                     Quant._update_available_quantity(ml.product_id, ml.location_id, -taken_from_untracked_qty,
    #                                                      lot_id=False, package_id=ml.package_id, owner_id=ml.owner_id,
    #                                                      width=ml.width, height=ml.height)
    #                     Quant._update_available_quantity(ml.product_id, ml.location_id, taken_from_untracked_qty,
    #                                                      lot_id=ml.lot_id, package_id=ml.package_id,
    #                                                      owner_id=ml.owner_id, width=ml.width, height=ml.height)
    #             Quant._update_available_quantity(ml.product_id, ml.location_dest_id, quantity, lot_id=ml.lot_id,
    #                                              package_id=ml.result_package_id, owner_id=ml.owner_id, in_date=in_date,
    #                                              width=ml.width, height=ml.height)
    #         ml_ids_to_ignore.add(ml.id)
    #     # Reset the reserved quantity as we just moved it to the destination location.
    #     mls_todo.with_context(bypass_reservation_update=True).write({
    #         'product_uom_qty': 0.00,
    #         'date': fields.Datetime.now(),
    #     })
