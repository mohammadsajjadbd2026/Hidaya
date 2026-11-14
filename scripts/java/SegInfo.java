import org.apache.lucene.codecs.*;import org.apache.lucene.index.*;import org.apache.lucene.store.*;import java.nio.file.*;import java.util.*;
public class SegInfo{public static void main(String[] a)throws Exception{Path p=Paths.get(a[0]);String seg=a[1];String fnmSuffix=a.length>2?a[2]:"";
 byte[] si=Files.readAllBytes(p.resolve(seg+".si"));int off=4;int n=si[off];off+=1+n+4;byte[] id=Arrays.copyOfRange(si,off,off+16);
 Directory dir=new NIOFSDirectory(p);Codec c=Codec.forName("Lucene104");SegmentInfo info=c.segmentInfoFormat().read(dir,seg,id,IOContext.DEFAULT);
 Directory cfs=info.getUseCompoundFile()?c.compoundFormat().getCompoundReader(dir,info):dir;
 FieldInfos fis=c.fieldInfosFormat().read(fnmSuffix.isEmpty()?cfs:dir,info,fnmSuffix,IOContext.DEFAULT);
 System.out.println(seg+" maxDoc="+info.maxDoc()+" compound="+info.getUseCompoundFile());
 for(FieldInfo f:fis)System.out.println("  "+f.number+" "+f.name+" dv="+f.getDocValuesType()+" idx="+f.getIndexOptions()+" dvGen="+f.getDocValuesGen());}}
