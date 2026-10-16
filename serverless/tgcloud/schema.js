import {table,text,integer,index} from 'sdk/db';
// Private persistent storage. No database object is exposed through an endpoint.
export const records=table('records',{
  id:text('id').primaryKey(),owner:integer('owner').notNull(),kind:text('kind').notNull(),
  body:text('body').notNull(),updated:integer('updated').notNull()
},t=>({ownerKind:index('records_owner_kind').on(t.owner,t.kind)}));
export const leases=table('leases',{
  id:text('id').primaryKey(),token:text('token').notNull(),until:integer('until').notNull()
});
export const aiUsage=table('ai_usage_v2',{
  id:text('id').primaryKey(),owner:integer('owner').notNull(),created:integer('created').notNull()
},t=>({ownerTime:index('usage_owner_time').on(t.owner,t.created)}));
export const receipts=table('update_receipts',{
  id:text('id').primaryKey(),created:integer('created').notNull()
});
