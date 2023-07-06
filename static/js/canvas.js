 window.onload = function() {
     var oC = document.getElementById('Can');
     var oCG = oC.getContext('2d');
     var img = new Image();
	        img.onload = function(){
				// 将图片画到canvas上面上去！
				oCG.drawImage(img,0,0);
			}
			img.src = "static/img/true/21_manual1.gif";
            oCG.strokeStyle='rgb(255,255,255).3';
     oC.onmousedown = function(ev) {
         var ev = ev || window.event;
         oCG.moveTo(ev.clientX - oC.offsetLeft, ev.clientY - oC.offsetTop); //ev.clientX-oC.offsetLeft,ev.clientY-oC.offsetTop鼠标在当前画布上X,Y坐标
         document.onmousemove = function(ev) {
             var ev = ev || window.event; //获取event对象
             oCG.lineTo(ev.clientX - oC.offsetLeft, ev.clientY - oC.offsetTop);
             oCG.stroke();
         };
         oC.onmouseup = function() {
             document.onmousemove = null;
             document.onmouseup = null;
         };
     };

 };