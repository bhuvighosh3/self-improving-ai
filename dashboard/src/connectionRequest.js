/** Bounded local requests. Submitted keys are never included in error text. */
export const SETTINGS_TIMEOUT_MS=10000;
export const CONNECTION_TEST_TIMEOUT_MS=15000;

export class ConnectionRequestError extends Error {
  constructor(message,kind="request"){super(message);this.kind=kind;}
}

export async function connectionRequest(path="",options={}) {
  return requestJson(`/api/portfolio/connections${path}`,options);
}

export async function requestJson(url,options={}) {
  const {signal,timeoutMs=SETTINGS_TIMEOUT_MS,
    timeoutMessage="The request timed out. You can try again or choose another model.",...fetchOptions}=options;
  const controller=new AbortController();
  let timedOut=false;
  const cancel=()=>controller.abort();
  if(signal?.aborted) controller.abort();
  else signal?.addEventListener("abort",cancel,{once:true});
  const timer=setTimeout(()=>{timedOut=true;controller.abort();},timeoutMs);
  try {
    const response=await fetch(url,{
      ...fetchOptions,signal:controller.signal,
      headers:{"Content-Type":"application/json",...fetchOptions.headers}
    });
    let data;
    try {data=await response.json();}
    catch(error) {
      if(controller.signal.aborted) throw error;
      throw new ConnectionRequestError("The local service returned an unreadable response. Try again.");
    }
    if(!response.ok) throw new ConnectionRequestError(typeof data.detail==="string"
      ? data.detail : "The request could not be completed. Check the input and try again.");
    return data;
  } catch(error) {
    if(timedOut) throw new ConnectionRequestError(timeoutMessage,"timeout");
    if(signal?.aborted) throw new ConnectionRequestError("Request cancelled.","cancelled");
    if(error instanceof ConnectionRequestError) throw error;
    throw new ConnectionRequestError("Could not reach the local service. Check that it is running and try again.","network");
  } finally {
    clearTimeout(timer);
    signal?.removeEventListener("abort",cancel);
  }
}

