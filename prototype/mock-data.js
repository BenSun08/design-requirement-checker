// Disposable fixture data. No document parsing or production matching occurs here.
window.MOCK_ITEMS = [
 ['自动退电屏蔽开关','电源管理','增加自动退电屏蔽开关','CONFIGURED','EXACT','增加自动退电屏蔽开关'],
 ['前挡风玻璃加热','加热与除霜','前挡风玻璃加热取消与除霜关联，修改加热时间为30分钟','CONFIGURED','NORMALIZED','前挡风玻璃加热 取消与除霜关联, 修改加热时间为 30 分钟'],
 ['GAG客户电动导板','导板控制','GAG客户电动导板增加正常高度伸出和缩回','MISSING',null,null],
 ['昼行灯状态判断','灯光控制','昼行灯将小灯开关状态判断改为小灯状态判断','STRUCK_OUT','EXACT','昼行灯将小灯开关状态判断改为小灯状态判断'],
 ['2门开导板报文判断','车门控制','2门开增加导板完全伸出、完全缩回报文判断','CONFIGURED','EXACT','2门开增加导板完全伸出、完全缩回报文判断'],
 ['2门控制延时','车门控制','2门控制增加开关门延时2s功能','CONFIGURED','EXACT','2门控制增加开关门延时3s功能'],
 ['小灯近光灯切换','灯光控制','小灯近光灯切换增加200ms滤波','CONFIGURED','EXACT','小灯近光灯切换增加200ms滤波'],
 ['导板正常高度判断','导板控制','导板控制增加正常高度判断','CONFIGURED','EXACT','导板控制增加正常高度判断'],
 ['侧标志灯功能','灯光控制','侧标志灯功能','CONFIGURED','ALIAS','侧标灯功能'],
 ['底盘工控完工反馈','导板控制','底盘工控完工反馈相关导板恢复条件','MISSING',null,null],
 ['中门警示灯','灯光控制','中门警示灯相关功能','CONFIGURED','EXACT','中门警示灯相关功能']
].map((r,i)=>({id:`fixture-${i+1}`,code:`DR-${String(i+1).padStart(3,'0')}`,name:r[0],category:r[1],expectedDescription:r[2],enabled:true,aliases:i===8?['侧标灯']:[],notes:'',fixture:{status:r[3],type:r[4],actual:r[5],changed:i===5,table:3,row:i+2,cell:2}}));
