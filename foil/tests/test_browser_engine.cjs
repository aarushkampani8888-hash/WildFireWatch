const fs=require('node:fs'),vm=require('node:vm'),cp=require('node:child_process'),assert=require('node:assert/strict');
const source=fs.readFileSync('frontend/simulation.js','utf8').replaceAll('export ','');
const context=vm.createContext({crypto:require('node:crypto').webcrypto,console});
vm.runInContext(source,context);
for(const params of [{},{wind:70,humidity:5,direction:90,horizon:120},{closures:['junction-south']},{closures:['community-junction','community-west']},{wind:0,humidity:100,horizon:30}]){
 const d={wind:24,humidity:22,direction:270,congestion:1.4,horizon:60,closures:[],weather_source:'scenario controls',...params};
 const browser=vm.runInContext('simulate('+JSON.stringify(d)+')',context);
 const server=JSON.parse(cp.execFileSync('python3',['-c','import json,sys;from engine import run;print(json.dumps(run(json.loads(sys.argv[1]))))',JSON.stringify(d)],{encoding:'utf8'}));
 assert.deepEqual(JSON.parse(JSON.stringify(browser.route)),server.route);
 browser.projections.forEach((p,i)=>assert.ok(Math.abs(p.a-server.projections[i].a)<1e-9));
}
console.log('5 browser/server parity scenarios passed');
