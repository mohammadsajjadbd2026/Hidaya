import org.apache.lucene.codecs.*;import org.apache.lucene.index.*;import org.apache.lucene.store.*;import java.nio.file.*;import java.util.*;import org.apache.lucene.search.DocIdSetIterator;
/** For a segment: count docs per "book" docvalue for the given book ids, and print docID min/max. usage: BookDocs dir seg fnmSuffix ids... */
public class BookDocs{public static void main(String[] a)throws Exception{Path p=Paths.get(a[0]);String seg=a[1];String sfx=a[2].equals("-")?"":a[2];
 Set<Long> want=new HashSet<>();for(int i=3;i<a.length;i++)want.add(Long.parseLong(a[i]));
 byte[] si=Files.readAllBytes(p.resolve(seg+".si"));int off=4;int n=si[off];off+=1+n+4;byte[] id=Arrays.copyOfRange(si,off,off+16);
 Directory dir=new NIOFSDirectory(p);Codec c=Codec.forName("Lucene104");SegmentInfo info=c.segmentInfoFormat().read(dir,seg,id,IOContext.DEFAULT);
 Directory cfs=info.getUseCompoundFile()?c.compoundFormat().getCompoundReader(dir,info):dir;
 FieldInfos all=c.fieldInfosFormat().read(sfx.isEmpty()?cfs:dir,info,sfx,IOContext.DEFAULT);
 FieldInfo bf=all.fieldInfo("book"); FieldInfos one=all;
 DocValuesProducer dvp=c.docValuesFormat().fieldsProducer(new SegmentReadState(cfs,info,one,IOContext.DEFAULT,""));
 NumericDocValues dv=dvp.getNumeric(bf);Map<Long,int[]> m=new TreeMap<>();
 for(int d=dv.nextDoc();d!=DocIdSetIterator.NO_MORE_DOCS;d=dv.nextDoc()){long b=dv.longValue();if(want.contains(b)){int[] r=m.computeIfAbsent(b,k->new int[]{0,Integer.MAX_VALUE,-1});r[0]++;r[1]=Math.min(r[1],d);r[2]=Math.max(r[2],d);}}
 for(var e:m.entrySet())System.out.println(seg+"\tbook="+e.getKey()+"\tdocs="+e.getValue()[0]+"\tdocRange="+e.getValue()[1]+"-"+e.getValue()[2]);}}
