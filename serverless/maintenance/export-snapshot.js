// Invoked only by the authenticated management API, never deployed as an endpoint.
import {db} from 'sdk';
export default async function () {
 const row=await db.get(`SELECT json_object(
  'columns',json_object(
   'records',json((SELECT json_group_array(name) FROM pragma_table_info('records'))),
   'ai_usage_v2',json((SELECT json_group_array(name) FROM pragma_table_info('ai_usage_v2')))),
  'tables',json_object(
   'records',json((SELECT json_group_array(json_object('id',id,'owner',owner,'kind',kind,'body',body,'updated',updated)) FROM (SELECT * FROM records ORDER BY id))),
   'ai_usage_v2',json((SELECT json_group_array(json_object('id',id,'owner',owner,'created',created)) FROM (SELECT * FROM ai_usage_v2 ORDER BY id))))
 ) AS snapshot`);
 return JSON.parse(row.snapshot);
}
