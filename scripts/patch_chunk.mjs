import {readFileSync} from 'node:fs';

process.setUncaughtExceptionCaptureCallback(error => {
  process.stderr.write(`${error.name}: ${error.message}\n`);
  process.exitCode = 1;
});

const input = JSON.parse(readFileSync(0, 'utf8'));
const source = input.source;
if (!source.startsWith('export const __rspack_esm_ids=')) throw Error('Unexpected chunk format');
// Pinned installed chunks export function tables. No module factory is invoked.
let chunk;
try { chunk = await import(`data:text/javascript;base64,${Buffer.from(source).toString('base64')}`); }
catch (error) { throw Error(`Installed chunk parse: ${error.message}`); }
if (Object.keys(chunk).sort().join(',') !== '__rspack_esm_ids,__webpack_modules__') {
  throw Error('Unexpected chunk exports');
}
let output = source;
const changes = [];
function replaceOne(text, before, after, label) {
  if (text.split(before).length !== 2) throw Error(`Expected one ${label} anchor`);
  return text.replace(before, () => after);
}
const runtime = 'globalThis.__codexComeBackLater';
for (const id of input.modules) {
  const original = chunk.__webpack_modules__[id]?.toString();
  if (!original) throw Error(`Missing factory ${id}`);
  let modified = original;
  if (id === 'oprL' && input.build === '27194') {
    if (!chunk.__webpack_modules__.CGsD?.toString().includes('titlePrefix:ts,secondaryContent:td')) {
      throw Error('Current row renderer no longer forwards titlePrefix');
    }
    modified = replaceOne(modified, 'oprL(e,t,n){', 'oprL(e,t,n){const __cblRequire=n;', '27194 row factory');
    modified = replaceOne(modified, 'function eN(e){let',
      'function eN(e){const __cblAccount=(0,r.Ul)(__cblRequire("SPnB").chatGptAuthenticatedAccountId$),'+
      '__cblHost=(0,r._U)(eI.yD,{conversationId:e.conversationId,hostId:e.hostId??e.threadSummary?.hostId??null})??G.fI,'+
      '__cblIdentity={accountId:__cblAccount,hostId:__cblHost,threadId:e.conversationId};'+
      'e='+runtime+'.useRow(d,__cblIdentity,e);let', '27194 row props');
    modified = replaceOne(modified, 'let nA=(0,eA.K)(tt),',
      'let nA=(0,eA.K)('+runtime+'.wrapMenu(tt,__cblIdentity)),', '27194 native menu');
  } else if (id === 'cojq' && input.build === '27194') {
    // Read the same scope follow-up and manager selector as the native dispatcher.
    const capture = 'function __cblCapture(scope,options){'+
      'const followUp=scope.get(a4.f),threadId=followUp?.type==="local"?followUp.localConversationId:null;'+
      'return '+runtime+'.capture(options,{accountId:scope.get(P.chatGptAuthenticatedAccountId$),'+
      'hostId:threadId==null?null:scope.get(S.qX,threadId),threadId});}';
    modified = replaceOne(modified, 'cojq(e,t,n){', 'cojq(e,t,n){'+capture, '27194 composer factory');
    modified = replaceOne(modified, 'oW=e=>{let t=dG?.variant',
      'oW=e=>{if('+runtime+'.isHuman(e))e=__cblCapture(lL,e);let t=dG?.variant', '27194 composer wrapper');
    modified = replaceOne(modified, 'addImageDataUrls:gT,queueAttachmentSubmit:w1,submit:w4',
      'addImageDataUrls:gT,queueAttachmentSubmit:w1,submit:w4,prepareHumanImageSubmit:e=>__cblCapture(lL,'+runtime+'.human(e))',
      '27194 image dependencies');
    modified = replaceOne(modified, 'queueAttachmentSubmit:d,submit:c}=w();if(null!=o)',
      'queueAttachmentSubmit:d,submit:c,prepareHumanImageSubmit:__cblPrepareImage}=w();l=__cblPrepareImage(l);if(null!=o)',
      '27194 image gesture before mask upload');
    const humanSubmit = 'e=>w4('+runtime+'.human(e))';
    modified = replaceOne(modified, 'stopRealtime:bb,submit:w4', 'stopRealtime:bb,submit:'+humanSubmit, '27194 keyboard');
    modified = replaceOne(modified, 'maybeSendQueuedSteerMessage:bM,submit:w4,submitButtonMode:',
      'maybeSendQueuedSteerMessage:bM,submit:'+humanSubmit+',submitButtonMode:', '27194 submit control');
    modified = replaceOne(modified, 'submitComposer:w4', 'submitComposer:'+humanSubmit, '27194 dictation');
    const paused = 'canShow:"local"===sG&&l2?.type==="local"&&!dr&&p9,submit:';
    modified = replaceOne(modified, paused+'e=>void w4({clear:e,focusComposerAfterSubmit:!0})',
      paused+'e=>void w4('+runtime+'.human({clear:e,focusComposerAfterSubmit:!0}))', '27194 paused queue confirmation');
    modified = replaceOne(modified, 'setIsSubmitting:d1,submit:e=>w4(e)}',
      'setIsSubmitting:d1,submit:'+humanSubmit+'}', '27194 goal replacement confirmation');
    const editor = '{followUpGesture:"primary",...e,focusComposerAfterSubmit:!0}';
    modified = replaceOne(modified, 'rt=e=>w4('+editor+')',
      'rt=e=>w4('+runtime+'.human('+editor+'))', '27194 editor submit');
    modified = replaceOne(modified, '},null!=V.additionalContextOverride',
      '},el='+runtime+'.attach(el,V,{accountId:e.get(P.chatGptAuthenticatedAccountId$)}),null!=V.additionalContextOverride', '27194 context ticket');
    // Local configuration readiness can outlive account/user selection.
    modified = replaceOne(modified, 'I.current={submit:e,submitTargetKey:v}',
      'I.current={submit:e,submitTargetKey:v,__cblAccount:e.type==="composer"&&'+runtime+
      '.isHuman(e.options)?[x.get(P.chatGptAuthenticatedAccountId$),x.get(P.o8)]:null}',
      '27194 configuration queue admission');
    modified = replaceOne(modified, 'case"composer":return void w(t.submit.options);',
      'case"composer":if(t.__cblAccount&&(t.__cblAccount[0]!==x.get(P.chatGptAuthenticatedAccountId$)||'+
      't.__cblAccount[1]!==x.get(P.o8)))return;return void w(t.submit.options);', '27194 configuration replay account guard');
    if (!modified.includes('(0,E.cI)(w6,()=>w4())')) throw Error('27194 automatic submit route changed');
  } else if (id === 'seW7') {
    const match = modified.match(/async function (\w+)\((\w+),(\w+)\)\{let (\w+)=\{\.\.\.\2,clientUserMessageId:/);
    if (!match) throw Error('Submission descriptor not found');
    const descriptor = match[4];
    const local = modified.match(/acceptLocally:(\w+)\.acceptLocally&&!(\w+),options:/);
    if (!local) throw Error('Local queue optimization not found');
    modified = replaceOne(modified, local[0],
      `acceptLocally:${local[1]}.acceptLocally&&!${local[2]}&&!${runtime}.requiresReceipt(${descriptor}.context),options:`, 'authoritative queue acknowledgement');
    const receipt = modified.match(/return"queued"===(\w+)\.status&&null!=(\w+)&&/);
    if (!receipt) throw Error('Submission result not found');
    modified = replaceOne(modified, receipt[0],
      `return await ${runtime}.accepted(${descriptor}.context,${receipt[1]},{hostId:${descriptor}.managerHostId,threadId:${descriptor}.targetConversationId}),`+receipt[0].slice(6), 'accepted result');
  } else throw Error(`Unreviewed module ${id}`);
  output = replaceOne(output, original, modified, `factory ${id}`);
  changes.push({module:id,beforeBytes:original.length,afterBytes:modified.length});
}
// Parse the patched export table without invoking its application factories.
try { await import(`data:text/javascript;base64,${Buffer.from(output).toString('base64')}`); }
catch (error) { throw Error(`Patched chunk parse: ${error.message}`); }
process.stdout.write(JSON.stringify({source:output,changes}));
